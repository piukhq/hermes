import json
import logging

import arrow
import sentry_sdk
from celery import shared_task
from django.conf import settings
from requests import HTTPError, request

from hermes.tasks import RetryTaskStore
from payment_card.enums import RequestMethod
from payment_card.models import PaymentAudit, PaymentStatus
from payment_card.payment import Payment, PaymentError
from scheme.models import SchemeAccount
from ubiquity.models import VopActivation
from ubiquity.utils import vop_deactivation_dict_by_payment_card_id


def retry_payment_void_task(transaction_data: dict) -> tuple[bool, str]:
    done = False
    try:
        scheme_acc = SchemeAccount.objects.get(pk=transaction_data["scheme_acc_id"])
        payment_audit = Payment.get_payment_audit(scheme_acc)
        if not payment_audit:
            err_msg = (
                f"scheme_account_id: {transaction_data['scheme_acc_id']} - No Payment Audit requiring voiding found"
            )
            logging.error(err_msg)
            # returns done as True to stop further retries
            done = True
            return done, err_msg

        Payment.attempt_void(payment_audit)
        done = True
        return done, "done"
    except PaymentError as e:
        sentry_sdk.capture_exception()
        return done, e.detail


@shared_task
def expired_payment_void_task() -> None:
    time_now = arrow.utcnow()
    statuses = (PaymentStatus.AUTHORISED, PaymentStatus.VOID_REQUIRED)
    payment_audits = PaymentAudit.objects.filter(
        status__in=statuses, created_on__lt=time_now.shift(seconds=-int(settings.PAYMENT_EXPIRY_TIME)).datetime
    )
    task_store = RetryTaskStore()
    tasks_in_queue = task_store.storage.lrange(task_store.task_list, 0, task_store.length)
    accounts_in_retry_queue = [json.loads(task)["scheme_acc_id"] for task in tasks_in_queue]

    for payment_audit in payment_audits:
        if (
            payment_audit.status == PaymentStatus.VOID_REQUIRED
            and payment_audit.scheme_account_id in accounts_in_retry_queue
        ):
            continue

        try:
            Payment.attempt_void(payment_audit)
        except PaymentError:
            transaction_data = {"scheme_acc_id": payment_audit.scheme_account_id}
            task_store.set_task("payment_card.tasks", "retry_payment_void_task", transaction_data)


@shared_task
def metis_delete_cards_and_activations(
    method: RequestMethod,
    endpoint: str,
    payload: dict,
    status: object = VopActivation.ACTIVATED,
    headers: dict | None = None,
) -> None:
    payload["activations"] = vop_deactivation_dict_by_payment_card_id(payload["id"], status)
    args = (
        method,
        endpoint,
        payload,
        headers,
    )
    metis_request(*args)


@shared_task
def metis_request(method: RequestMethod, endpoint: str, payload: dict, headers: dict | None = None) -> None:
    base_headers = {
        "Authorization": f"Token {settings.SERVICE_API_KEY}",
        "Content-Type": "application/json",
        "X-azure-ref": None,
    }
    if headers:
        base_headers["X-azure-ref"] = headers.get("X-azure-ref", None)
        if "X-Priority" in headers:
            base_headers["X-Priority"] = headers["X-Priority"]

    response = request(
        method.value,
        settings.METIS_URL + endpoint,
        json=payload,
        headers=base_headers,
    )
    try:
        response.raise_for_status()
    except HTTPError:
        sentry_sdk.capture_exception()
