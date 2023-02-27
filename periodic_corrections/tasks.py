import json
import logging
from datetime import timedelta

import arrow
from celery import shared_task
from django.conf import settings

from payment_card.enums import RequestMethod
from payment_card.models import PaymentCardAccount
from scripts.actions.metis_foundation import metis_foundation_request

from .models import PeriodicRetain, RetryStatus

logger = logging.getLogger(__name__)
"""
To install periodic corrections load this module into hermes in root folder  periodic_corrections
-----------------------
In hermes.settings add lines:
# Time in seconds for periodic corrections to be called by celery beats
PERIODIC_CORRECTIONS_PERIOD = env_var("PERIODIC_CORRECTIONS_PERIOD", "600")
RETAIN_FROM_MINUTES = int(env_var("RETAIN_FROM_MINUTES", "-720"))
RETAIN_TO_MINUTES = int(env_var("RETAIN_TO_MINUTES", "-20"))

also add to list of local modules:

LOCAL_APPS = (
    .........
    "periodic_corrections",
)

------------------------
In hermes.celery add to variable definitions:
app.autodiscover_tasks(
    [
        ........
        "periodic_corrections.tasks",
        ......
    ]
app.conf.beat_schedule = {
    ............
    "periodic_corrections_tasks": {
        "task": "periodic_corrections.tasks.retain_pending_payments",
        "schedule": int(settings.PERIODIC_CORRECTIONS_PERIOD),
        "args": (),
    },
------------------------
"""


@shared_task
def retain_pending_payments():
    utc = arrow.utcnow()
    from_time = utc.shift(minutes=settings.RETAIN_FROM_MINUTES).format()
    to_time = utc.shift(minutes=settings.RETAIN_TO_MINUTES).format()
    new_accounts = PaymentCardAccount.objects.filter(
        status=PaymentCardAccount.PENDING, updated__range=[from_time, to_time], periodicretain=None
    )

    logger.info(f"checking for pending payments from {from_time} to {to_time} found {len(new_accounts)}")
    for account in new_accounts:
        PeriodicRetain.objects.create(payment_card_account=account, status=RetryStatus.RETRYING, retry_count=0)

    periodic_retains = PeriodicRetain.objects.filter(status=RetryStatus.RETRYING)
    logger.info(f"Found {len(periodic_retains)} periodic retain retries to process")

    for periodic_retain in periodic_retains:
        retain_retry(periodic_retain)


def retain_retry(periodic_retain: PeriodicRetain) -> None:
    periodic_retain.retry_count += 1
    status_code = 0
    reason = ""
    try:
        reply = retain_via_foundation(periodic_retain.payment_card_account)

    except Exception as e:
        status_code = 0
        reason = f"Exception {e}"
        reply = None

    try:
        reply_json = json.loads(reply.get("resp_text", {}))
        transaction = reply_json.get("transaction", {})
    except Exception:
        transaction = {}

    if reply:
        status_code = reply.get("status_code", 0)
        reason = reply.get("reason", "")

    message_key = transaction.get("message_key", "")
    message = transaction.get("message", "")
    succeeded = transaction.get("succeeded", False)
    pay_method = transaction.get("payment_method", {})
    storage_state = pay_method.get("storage_state", "")

    if status_code == 200:
        periodic_retain.status = RetryStatus.SUCCESSFUL
    elif (arrow.get(periodic_retain.created) - arrow.utcnow() < timedelta(minutes=settings.RETAIN_FROM_MINUTES)) or (
        message_key == "messages.unable_to_retain_since_storage_state_is_redacted"
    ):
        periodic_retain.status = RetryStatus.STOPPED

    periodic_retain.message_key = message_key
    periodic_retain.succeeded = succeeded

    entry = [status_code, reason, succeeded, message_key, message, storage_state]
    titles = ["status:", "reason:", "succeeded:", "message key:", "message:", "storage:"]
    result_dict = formated_results_entry(periodic_retain, entry, titles)
    periodic_retain.results.insert(0, result_dict)
    periodic_retain.save()


def formated_results_entry(periodic_retain: PeriodicRetain, entry: list, titles: list) -> dict:
    items = ", ".join([f"{titles[index]} {entry[index]}" for index in range(0, len(entry)) if entry[index]])
    result_dict = {"repeated": 0, "results": items}
    if periodic_retain.results:
        last_entry = periodic_retain.results.pop(0)
        if last_entry.get("results") == items:
            result_dict = last_entry
            repeated = result_dict.get("repeated", 0) + 1
            result_dict["repeated"] = repeated
            result_dict["results"] = last_entry["results"]
        else:
            periodic_retain.results.insert(0, last_entry)
    result_dict["retry"] = periodic_retain.retry_count
    return result_dict


def retain_via_foundation(account: PaymentCardAccount) -> object:
    data = {"payment_token": account.token, "id": account.id}
    reply = metis_foundation_request(
        RequestMethod.POST, f"/foundation/spreedly/{account.payment_card.slug}/retain", data
    )
    return reply
