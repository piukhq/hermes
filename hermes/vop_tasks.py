import requests
from celery import shared_task
from django.conf import settings

from prometheus_client import push_to_gateway

from periodic_retry.models import RetryTaskList, PeriodicRetryStatus
from periodic_retry.tasks import PeriodicRetryHandler
from prometheus.metrics import registry, vop_activation_status


def vop_activate_request(activation):
    data = {
        'payment_token': activation.payment_card_account.psp_token,
        'partner_slug': 'visa',
        'merchant_slug': activation.scheme.slug,
        'id': activation.payment_card_account.id        # improves tracking via logs esp. in Metis
    }

    send_activation.delay(activation, data)


def process_result(rep, activation, link_action):
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
        if activation_id and link_action == activation.ACTIVATING:
            activation.activation_id = activation_id
            activation.status = activation.ACTIVATED
            activation.save()
            vop_activation_status.labels(status='Activating').dec(1)
            vop_activation_status.labels(status='Activated').inc()
            push_to_gateway(settings.PROMETHEUS_PUSH_GATEWAY, job='hermes', registry=registry)

        elif link_action == activation.DEACTIVATING:
            # todo May be try periodic delete or delete it now instead of save
            activation.status = activation.DEACTIVATED
            activation.save()
            vop_activation_status.labels(status='Deactivating').dec(1)
            vop_activation_status.labels(status='Deactivated').inc()
            push_to_gateway(settings.PROMETHEUS_PUSH_GATEWAY, job='hermes', registry=registry)

        status = PeriodicRetryStatus.SUCCESSFUL
        return status, response_data
    else:
        if response_status != "Retry":
            status = PeriodicRetryStatus.FAILED
    return status, response_data


def activate(activation, data: dict):
    activation.status = activation.ACTIVATING
    activation.save()
    rep = requests.post(settings.METIS_URL + '/visa/activate/',
                        json=data,
                        headers={'Authorization': 'Token {}'.format(settings.SERVICE_API_KEY),
                                 'Content-Type': 'application/json'})

    vop_activation_status.labels(status=activation.VOP_STATUS[activation.ACTIVATING][1]).inc()
    push_to_gateway(settings.PROMETHEUS_PUSH_GATEWAY, job='hermes', registry=registry)

    return process_result(rep, activation, activation.ACTIVATING)


@shared_task
def send_activation(activation, data: dict):
    status, result = activate(activation, data)
    if status == PeriodicRetryStatus.REQUIRED:
        PeriodicRetryHandler(task_list=RetryTaskList.METIS_REQUESTS).new(
            'ubiquity.tasks', 'retry_activation',
            context={"activation_id": activation.id, "post_data": data},
            retry_kwargs={"max_retry_attempts": 100, "results": [result]}
        )
    elif status == PeriodicRetryStatus.FAILED:
        PeriodicRetryHandler(task_list=RetryTaskList.METIS_REQUESTS).new(
            'ubiquity.tasks', 'retry_activation',
            context={"activation_id": activation.id, "post_data": data},
            retry_kwargs={"max_retry_attempts": 0, "status": PeriodicRetryStatus.FAILED, "results": [result]}
        )


def deactivate(activation, data: dict):
    activation.status = activation.DEACTIVATING
    activation.save()
    rep = requests.post(settings.METIS_URL + '/visa/deactivate/',
                        json=data,
                        headers={'Authorization': 'Token {}'.format(settings.SERVICE_API_KEY),
                                 'Content-Type': 'application/json'})
    return process_result(rep, activation, activation.DEACTIVATING)


@shared_task
def send_deactivation(activation):
    data = {
        'payment_token': activation.payment_card_account.psp_token,
        'partner_slug': 'visa',
        'activation_id': activation.activation_id,
        'id': activation.payment_card_account.id        # improves tracking via logs esp. in Metis
    }
    status, result = deactivate(activation, data)

    if status == PeriodicRetryStatus.REQUIRED:
        PeriodicRetryHandler(task_list=RetryTaskList.METIS_REQUESTS).new(
            'ubiquity.tasks', 'retry_deactivation',
            context={"activation_id": activation.id, "post_data": data},
            retry_kwargs={"max_retry_attempts": 100, "results": [result]}
        )
    elif status == PeriodicRetryStatus.FAILED:
        PeriodicRetryHandler(task_list=RetryTaskList.METIS_REQUESTS).new(
            'ubiquity.tasks', 'retry_deactivation',
            context={"activation_id": activation.id, "post_data": data},
            retry_kwargs={"max_retry_attempts": 0, "status": PeriodicRetryStatus.FAILED, "results": [result]}
        )
