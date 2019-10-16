import json
import logging

import sentry_sdk
import arrow
from celery import shared_task

from hermes.settings import PAYMENT_EXPIRY_TIME
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
            err_msg = "scheme_account_id: {} - No Payment Audit found".format(transaction_data['scheme_acc_id'])
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
        created_on__lt=time_now.replace(seconds=-int(PAYMENT_EXPIRY_TIME)).datetime
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