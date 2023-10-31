from typing import TYPE_CHECKING

import requests
from celery import shared_task
from django.conf import settings

from history.signals import HISTORY_CONTEXT
from history.utils import clean_history_kwargs, set_history_kwargs
from payment_card.models import VopMerchantGroup
from periodic_retry.models import PeriodicRetryStatus, RetryTaskList
from periodic_retry.tasks import PeriodicRetryHandler

if TYPE_CHECKING:
    from ubiquity.models import VopActivation


def vop_activate_request(activation: "VopActivation") -> None:
    merchant_group = VopMerchantGroup.cached_group_lookup(activation.scheme.vop_merchant_group_id)
    data: dict[str, str | int] = {
        "payment_token": activation.payment_card_account.psp_token,
        "partner_slug": "visa",
        "offer_id": merchant_group.offer_id,
        "merchant_group": merchant_group.group_name,
        "merchant_slug": activation.scheme.slug,
        "id": activation.payment_card_account.id,  # improves tracking via logs esp. in Metis
    }

    try:
        history_kwargs = {"user_info": HISTORY_CONTEXT.user_info}
    except AttributeError:
        history_kwargs = None
    send_activation.delay(activation, data, history_kwargs)


def process_result(
    resp: requests.Response, activation: "VopActivation", link_action: int
) -> tuple[PeriodicRetryStatus, dict]:
    status = PeriodicRetryStatus.REQUIRED
    ret_data: dict[str, str] = resp.json()
    response_status = ret_data.get("response_status")
    activation_id = ret_data.get("activation_id")

    response_data = {
        "agent_response_code": ret_data.get("agent_response_code", ""),
        "agent_response_message": ret_data.get("agent_response_message", ""),
    }

    if activation_id:
        response_data["activation_id"] = activation_id

    if resp.status_code == 201:
        if activation_id and link_action == activation.ACTIVATING:
            activation.activation_id = activation_id
            activation.status = activation.ACTIVATED
            activation.save(update_fields=["activation_id", "status"])

        elif link_action == activation.DEACTIVATING:
            # todo May be try periodic delete or delete it now instead of save
            activation.status = activation.DEACTIVATED
            activation.save(update_fields=["status"])

        status = PeriodicRetryStatus.SUCCESSFUL
        return status, response_data
    else:
        if response_status != "Retry":
            status = PeriodicRetryStatus.FAILED

    return status, response_data


def activate(activation: "VopActivation", data: dict) -> tuple[PeriodicRetryStatus, dict]:
    if activation.status != activation.ACTIVATING:
        activation.status = activation.ACTIVATING
        activation.save(update_fields=["status"])

    resp = requests.post(
        settings.METIS_URL + "/visa/activate/",
        json=data,
        headers={"Authorization": "Token {}".format(settings.SERVICE_API_KEY), "Content-Type": "application/json"},
    )

    return process_result(resp, activation, activation.ACTIVATING)


@shared_task
def send_activation(activation: "VopActivation", data: dict, history_kwargs: dict | None = None) -> None:
    set_history_kwargs(history_kwargs)
    status, result = activate(activation, data)
    if status == PeriodicRetryStatus.REQUIRED:
        PeriodicRetryHandler(task_list=RetryTaskList.METIS_REQUESTS).new(
            "ubiquity.tasks",
            "retry_activation",
            context={"activation_id": activation.id, "post_data": data},
            retry_kwargs={"max_retry_attempts": 100, "results": [result]},
        )
    elif status == PeriodicRetryStatus.FAILED:
        PeriodicRetryHandler(task_list=RetryTaskList.METIS_REQUESTS).new(
            "ubiquity.tasks",
            "retry_activation",
            context={"activation_id": activation.id, "post_data": data},
            retry_kwargs={"max_retry_attempts": 0, "status": PeriodicRetryStatus.FAILED, "results": [result]},
        )

    clean_history_kwargs(history_kwargs)


def deactivate(
    activation: "VopActivation", data: dict, headers: dict | None = None
) -> tuple[PeriodicRetryStatus, dict]:
    activation.status = activation.DEACTIVATING
    activation.save(update_fields=["status"])

    rep = requests.post(
        settings.METIS_URL + "/visa/deactivate/",
        json=data,
        headers={
            "Authorization": "Token {}".format(settings.SERVICE_API_KEY),
            "Content-Type": "application/json",
            "X-azure-ref": headers.get("X-azure-ref", None) if headers else None,
        },
    )
    return process_result(rep, activation, activation.DEACTIVATING)


@shared_task
def send_deactivation(
    activation: "VopActivation", history_kwargs: dict | None = None, headers: dict | None = None
) -> None:
    merchant_group = VopMerchantGroup.cached_group_lookup(activation.scheme.vop_merchant_group_id)
    set_history_kwargs(history_kwargs)
    data = {
        "payment_token": activation.payment_card_account.psp_token,
        "partner_slug": "visa",
        "offer_id": merchant_group.offer_id,
        "activation_id": activation.activation_id,
        "id": activation.payment_card_account.id,  # improves tracking via logs esp. in Metis
    }
    status, result = deactivate(activation, data, headers=headers)

    if status == PeriodicRetryStatus.REQUIRED:
        PeriodicRetryHandler(task_list=RetryTaskList.METIS_REQUESTS).new(
            "ubiquity.tasks",
            "retry_deactivation",
            context={"activation_id": activation.id, "post_data": data},
            retry_kwargs={"max_retry_attempts": 100, "results": [result]},
        )
    elif status == PeriodicRetryStatus.FAILED:
        PeriodicRetryHandler(task_list=RetryTaskList.METIS_REQUESTS).new(
            "ubiquity.tasks",
            "retry_deactivation",
            context={"activation_id": activation.id, "post_data": data},
            retry_kwargs={"max_retry_attempts": 0, "status": PeriodicRetryStatus.FAILED, "results": [result]},
        )
    clean_history_kwargs(history_kwargs)
