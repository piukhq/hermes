import json
import logging

import arrow
import sentry_sdk
from celery import shared_task
from django.conf import settings
from requests import request

from hermes.tasks import RetryTaskStore
from payment_card.models import PaymentAudit, PaymentStatus
from payment_card.payment import Payment, PaymentError
from scheme.models import SchemeAccount


def retry_payment_void_task(transaction_data: dict) -> (bool, str):
    done = False
    try:
        scheme_acc = SchemeAccount.objects.get(pk=transaction_data['scheme_acc_id'])
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
        status__in=statuses,
        created_on__lt=time_now.shift(seconds=-int(settings.PAYMENT_EXPIRY_TIME)).datetime
    )
    task_store = RetryTaskStore()
    tasks_in_queue = task_store.storage.lrange(task_store.task_list, 0, task_store.length)
    accounts_in_retry_queue = [json.loads(task)['scheme_acc_id'] for task in tasks_in_queue]

    for payment_audit in payment_audits:
        if (payment_audit.status == PaymentStatus.VOID_REQUIRED
                and payment_audit.scheme_account_id in accounts_in_retry_queue):
            continue

        try:
            Payment.attempt_void(payment_audit)
        except PaymentError:
            transaction_data = {'scheme_acc_id': payment_audit.scheme_account_id}
            task_store.set_task('payment_card.tasks', 'retry_payment_void_task', transaction_data)


@shared_task
def async_metis_request(method: str, endpoint: str, payload: dict) -> None:
    request(
        method,
        settings.METIS_URL + endpoint,
        json=payload,
        headers={
            'Authorization': 'Token {}'.format(settings.SERVICE_API_KEY),
            'Content-Type': 'application/json'
        }
    )
