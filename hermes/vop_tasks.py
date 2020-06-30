from typing import Iterable

import requests
from celery import shared_task
from django.conf import settings
from periodic_retry.models import RetryTaskList, PeriodicRetryStatus
from periodic_retry.tasks import PeriodicRetryHandler
# from ubiquity.models import PaymentCardSchemeEntry


def vop_activate_by_link(link: "ubiquity.models.PaymentCardSchemeEntry",
                         activation: "ubiquity.models.VopActivations"
                         ):
    # todo remove vop_link status on entry table
    link.vop_link = link.ACTIVATING
    link.save()

    # for convenience the link is used to get payment_card_account and slug but should imply this is called for
    # every active visa link only for those not already activated in VopActivation model

    data = {
        'payment_token': entry.payment_card_account.psp_token,
        'partner_slug': 'visa',
        'merchant_slug': entry.scheme_account.scheme.slug
    }

    send_activation.delay(activation, data)


def deactivate_delete_link(entry: "ubiquity.models.PaymentCardSchemeEntry"):
    # Todo: correct this!
    if entry.payment_card_account.payment_card.slug == "visa":
        send_deactivation.delay(entry)
    else:
        entry.delete()


def deactivate_vop_list(entries: Iterable["ubiquity.models.PaymentCardSchemeEntry"]):
    # Todo: correct this!
    # pass list and send to deactivate.
    for entry in entries:
        send_deactivation.delay(entry)


def retry_activation(data):
    from ubiquity.models import VopActivations
    retry_obj = data["periodic_retry_obj"]
    activation = VopActivations.objects.get(id=data['context']['activation_id'])
    status, result = activate(activation, data['context']['post_data'])
    retry_obj.status = status
    retry_obj.results += [result]


def process_result(rep, activation, link_action):
    # Todo: correct this!
    status = PeriodicRetryStatus.REQUIRED
    ret_data = rep.json()
    response_status = ret_data.get("response_status")
    activation_id = ret_data.get("activation_id")

    response_data = {
        "agent_response_code": ret_data.get("agent_response_code", ""),
        "agent_response_message": ret_data.get("agent_response_message", "")
    }

    if activation_id:
        response_data['activation_id'] = activation_id

    if rep.status_code == 201:
        entry.vop_link = link_action
        entry.save()
        if link_action == activation.ACTIVATING and activation_id:
            activation.activation_id = activation_id
            activation.status = activation.ACTIVATED
            activation.save()
        status = PeriodicRetryStatus.SUCCESSFUL
        return status, response_data
    else:
        if response_status != "Retry":
            status = PeriodicRetryStatus.FAILED
    return status, response_data


def activate(activation: "ubiquity.models.VopActivations", data: dict):
    rep = requests.post(settings.METIS_URL + '/visa/activate/',
                        json=data,
                        headers={'Authorization': 'Token {}'.format(settings.SERVICE_API_KEY),
                                 'Content-Type': 'application/json'})
    return process_result(rep, activation, activation.ACTIVATING)


@shared_task
def send_activation(activation: "ubiquity.models.VopActivations", data: dict):
    status, result = activate(activation, data)
    if status == PeriodicRetryStatus.REQUIRED:
        PeriodicRetryHandler(task_list=RetryTaskList.METIS_REQUESTS).new(
            'hermes.vop_tasks', 'retry_activation',
            context={"activation_id": activation.id, "post_data": data},
            retry_kwargs={"max_retry_attempts": 100, "results": [result]}
        )
    elif status == PeriodicRetryStatus.FAILED:
        PeriodicRetryHandler(task_list=RetryTaskList.METIS_REQUESTS).new(
            'hermes.vop_tasks', 'retry_activation',
            context={"activation_id": activation.id, "post_data": data},
            retry_kwargs={"max_retry_attempts": 0, "status": PeriodicRetryStatus.FAILED, "results": [result]}
        )


def deactivate(entry: "ubiquity.models.PaymentCardSchemeEntry", data: dict):
    rep = requests.post(settings.METIS_URL + '/visa/deactivate/',
                        json=data,
                        headers={'Authorization': 'Token {}'.format(settings.SERVICE_API_KEY),
                                 'Content-Type': 'application/json'})
    return process_result(rep, entry, PaymentCardSchemeEntry.DEACTIVATED)


def retry_deactivation(data):
    # Todo: correct this!
    retry_obj = data["periodic_retry_obj"]
    entry = PaymentCardSchemeEntry.objects.get(id=data['context']['entry_id'])
    status, result = deactivate(entry, data['context']['post_data'])
    if status == PeriodicRetryStatus.SUCCESSFUL:
        entry.delete()
    retry_obj.status = status
    retry_obj.results += [result]


@shared_task
def send_deactivation(entry: "ubiquity.models.PaymentCardSchemeEntry"):
    # Todo: correct this!
    entry.vop_link = entry.DEACTIVATING
    entry.save()
    data = {
        'payment_token': entry.payment_card_account.psp_token,
        'partner_slug': 'visa',
        'activation_id': entry.payment_card_account.activation_id,
        # 'association_id': entry.id,
        # 'payment_card_account_id': entry.payment_card_account.id,
        # 'scheme_account_id': entry.scheme_account.id
    }
    status, result = deactivate(entry, data)

    if status == entry.SUCCESSFUL:
        entry.delete()
    elif status == PeriodicRetryStatus.REQUIRED:
        PeriodicRetryHandler(task_list=RetryTaskList.METIS_REQUESTS).new(
            'hermes.vop_tasks', 'retry_deactivation',
            context={"entry_id": entry.id, "post_data": data},
            retry_kwargs={"max_retry_attempts": 100, "results": [result]}
        )
    elif status == PeriodicRetryStatus.FAILED:
        PeriodicRetryHandler(task_list=RetryTaskList.METIS_REQUESTS).new(
            'hermes.vop_tasks', 'retry_deactivation',
            context={"entry_id": entry.id, "post_data": data},
            retry_kwargs={"max_retry_attempts": 0, "status": PeriodicRetryStatus.FAILED, "results": [result]}
        )
