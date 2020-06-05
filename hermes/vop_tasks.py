from typing import Iterable

import requests
from celery import shared_task
from django.conf import settings
from periodic_retry.models import RetryTaskList, PeriodicRetryStatus
from periodic_retry.tasks import PeriodicRetryHandler
from ubiquity.models import PaymentCardSchemeEntry


def vop_check_scheme(scheme_account):
    """ This method finds all the visa payment cards linked to this scheme account with undefined VOP status
    """
    # Must import here to avoid circular imports in future consider moving status definitions outside of model
    from payment_card.models import PaymentCardAccount

    entries = PaymentCardSchemeEntry.objects.filter(
        scheme_account=scheme_account,
        payment_card_account__status=PaymentCardAccount.ACTIVE,
        payment_card_account__payment_card__slug="visa",
        vop_link=PaymentCardSchemeEntry.UNDEFINED
    )

    if entries:
        vop_activate(entries)


def vop_activate(entries: Iterable[PaymentCardSchemeEntry]):

    for entry in entries:
        entry.vop_link = PaymentCardSchemeEntry.ACTIVATING
        entry.save()

        data = {
            'payment_token': entry.payment_card_account.psp_token,
            'partner_slug': entry.scheme_account.scheme.slug,
            'association_id': entry.id,
            'payment_card_account_id': entry.payment_card_account.id,
            'scheme_account_id': entry.scheme_account.id
        }

        send_activation.delay(entry, data)


def deactivate_delete_link(entry: PaymentCardSchemeEntry):
    if entry.payment_card_account.payment_card.slug == "visa":
        send_deactivation.delay(entry)
    else:
        entry.delete()


def deactivate_vop_list(entries: Iterable[PaymentCardSchemeEntry]):
    # pass list and send to deactivate.
    for entry in entries:
        send_deactivation.delay(entry)


def retry_activation(data):
    retry_obj = data["periodic_retry_obj"]
    entry = PaymentCardSchemeEntry.objects.get(id=data['context']['entry_id'])
    status, result = activate(entry, data['context']['post_data'])
    retry_obj.status = status
    retry_obj.results += [result]


def process_result(rep, entry, link_action):
    status = PeriodicRetryStatus.REQUIRED
    ret_data = rep.json()
    response_status = ret_data.get("response_status")
    agent_response_code = ret_data.get("agent_response_code")
    if rep.status_code == 201:
        entry.vop_link = link_action
        entry.save()
        status = PeriodicRetryStatus.SUCCESSFUL
        return status, agent_response_code
    else:
        if response_status != "Retry":
            status = PeriodicRetryStatus.FAILED
    return status, agent_response_code


def activate(entry: PaymentCardSchemeEntry, data: dict):
    rep = requests.post(settings.METIS_URL + '/visa/activate/',
                        json=data,
                        headers={'Authorization': 'Token {}'.format(settings.SERVICE_API_KEY),
                                 'Content-Type': 'application/json'})
    return process_result(rep, entry, PaymentCardSchemeEntry.ACTIVATED)


@shared_task
def send_activation(entry: PaymentCardSchemeEntry, data: dict):
    status, _ = activate(entry, data)
    if status == PeriodicRetryStatus.REQUIRED:
        PeriodicRetryHandler(task_list=RetryTaskList.METIS_REQUESTS).new(
            'hermes.vop_tasks', 'retry_activation',
            context={"entry_id": entry.id, "post_data": data},
            retry_kwargs={"max_retry_attempts": 100}
        )


def deactivate(entry: PaymentCardSchemeEntry, data: dict):
    rep = requests.post(settings.METIS_URL + '/visa/deactivate/',
                        json=data,
                        headers={'Authorization': 'Token {}'.format(settings.SERVICE_API_KEY),
                                 'Content-Type': 'application/json'})
    return process_result(rep, entry, PaymentCardSchemeEntry.DEACTIVATED)


def retry_deactivation(data):
    retry_obj = data["periodic_retry_obj"]
    entry = PaymentCardSchemeEntry.objects.get(id=data['context']['entry_id'])
    status, result = deactivate(entry, data['context']['post_data'])
    if status == PeriodicRetryStatus.SUCCESSFUL:
        entry.delete()
    retry_obj.status = status
    retry_obj.results += [result]


@shared_task
def send_deactivation(entry: PaymentCardSchemeEntry):
    entry.vop_link = PaymentCardSchemeEntry.DEACTIVATING
    entry.save()
    data = {
        'payment_token': entry.payment_card_account.psp_token,
        'partner_slug': entry.scheme_account.scheme.slug,
        'association_id': entry.id,
        'payment_card_account_id': entry.payment_card_account.id,
        'scheme_account_id': entry.scheme_account.id
    }
    status, _ = deactivate(entry, data)

    if status == PeriodicRetryStatus.SUCCESSFUL:
        entry.delete()
    elif status == PeriodicRetryStatus.REQUIRED:
        PeriodicRetryHandler(task_list=RetryTaskList.METIS_REQUESTS).new(
            'hermes.vop_tasks', 'retry_deactivation',
            context={"entry_id": entry.id, "post_data": data},
            retry_kwargs={"max_retry_attempts": 100}
        )
