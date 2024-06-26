# Generated by Django 4.0.7 on 2022-09-20 08:44

import logging
from time import sleep
from uuid import uuid4

from celery import shared_task
from django.conf import settings
from django.db import migrations, models
from django.db.utils import OperationalError
from redis.client import Redis

import ubiquity.models
from ubiquity.models import SchemeAccountEntry

TASK_SIZE = 500
MIGRATION_TASK_PREFIX = "hermes-migration-pll-data-"
r_write = Redis(connection_pool=settings.REDIS_WRITE_API_CACHE_POOL)
r_read = Redis(connection_pool=settings.REDIS_READ_API_CACHE_POOL)


def retry_redis(action, key):
    for x in range(5):
        try:
            redis_key = MIGRATION_TASK_PREFIX + key
            if action == "set":
                r_write.set(redis_key, "True")
            elif action == "delete":
                r_write.delete(redis_key)
            else:
                raise ValueError(f"retry redis func only accepts set or delete, received {action}")
            break
        except Exception as e:
            if x == 4:
                logging.warning(f"redis delete failed 5 times in a row, no more retries, error: {e!r}")
                raise
            logging.warning(f"redis delete broke with exception {e!r}, retrying...")
            sleep(0.2)


def retry_celery(task_id, pks_to_process, status=None, status_mapping=None):
    for x in range(5):
        try:
            if status:
                populate_link_task.delay(task_id, pks_to_process, status=status)
            else:
                populate_link_task.delay(task_id, pks_to_process, status_mapping=status_mapping)
            break
        except Exception as e:
            if x == 4:
                logging.warning(f"celery delay failed 5 times in a row, no more retries, error: {e!r}")
                raise
            logging.warning(f"celery delay broke with exception {e!r}, retrying...")
            sleep(0.2)


def wallet_only_process(pks_to_process, status):
    for attempt in range(3):
        try:
            entries_to_process = SchemeAccountEntry.objects.filter(id__in=pks_to_process)
            entries_to_process.update(link_status=status)
            break
        except OperationalError:
            logging.warning(f"Database connection failed!, retrying {2 - attempt} more times...")
            if attempt == 2:
                raise
            sleep(0.2)


def non_wallet_only_process(pks_to_process, status_mapping):
    for attempt in range(3):
        try:
            entries_to_process = list(SchemeAccountEntry.objects.filter(id__in=pks_to_process))
            break
        except OperationalError:
            logging.warning(f"Database connection failed!, retrying {2 - attempt} more times...")
            if attempt == 2:
                raise
            sleep(0.2)

    bulk_update_cache = []
    for entry in entries_to_process:
        entry.link_status = status_mapping[entry.id]
        bulk_update_cache.append(entry)

    for attempt in range(3):
        try:
            SchemeAccountEntry.objects.bulk_update(bulk_update_cache, ["link_status"])
            break
        except OperationalError:
            logging.warning(f"Database connection failed!, retrying {2 - attempt} more times...")
            if attempt == 2:
                raise
            sleep(0.2)


@shared_task
def populate_link_task(task_id, pks_to_process, status=None, status_mapping=None):
    try:
        if status:
            wallet_only_process(pks_to_process, status)
        else:
            non_wallet_only_process(pks_to_process, status_mapping)
        # do proper retries if this actually speeds things up
        retry_redis("delete", task_id)

    except Exception as e:
        logging.warning(
            f"Migration task failed! Migration: '{__file__}', error: {e!r}, "
            f"Migration will stay locked until this is manually pushed through. To do this, run 'populate_link_task'"
            f"with these arguments: task_id = '{task_id}', pks_to_process = '{pks_to_process}'."
            f"And these keyword arguments: status={status} status_mapping={status_mapping}"
        )
        raise


def wait_for_tasks_to_finish():
    tasks_to_process = True
    while tasks_to_process:
        try:
            tasks_to_process = len(list(r_read.scan_iter(f"{MIGRATION_TASK_PREFIX}*")))
            logging.warning(f"Waiting for async migration to complete, {tasks_to_process} tasks remaining")
            if tasks_to_process:
                sleep(2)
        except Exception as e:
            logging.warning(
                f"Unexpected error happened while checking remaining tasks! I'll keep checking until"
                f"this gets resolved! Error: {e!r}"
            )


def get_wallet_only_entries(SchemeAccountEntry, sql_offset, sql_limit):
    for attempt in range(3):
        try:
            pks_to_process = list(
                SchemeAccountEntry.objects.filter(auth_provided=False)
                .order_by("id")[sql_offset:sql_limit]
                .values_list("id", flat=True)
            )
            break
        except OperationalError:
            logging.warning(f"Database connection failed!, retrying {2 - attempt} more times...")
            if attempt == 2:
                raise
            sleep(0.2)

    return pks_to_process


def get_non_wallet_only_entries(SchemeAccountEntry, sql_offset, sql_limit):
    for attempt in range(3):
        try:
            entries = list(
                SchemeAccountEntry.objects.filter(auth_provided=True)
                .order_by("id")
                .select_related("scheme_account")[sql_offset:sql_limit]
                .values("id", "scheme_account__status")
            )
            break
        except OperationalError:
            logging.warning(f"Database connection failed!, retrying {2 - attempt} more times...")
            if attempt == 2:
                raise
            sleep(0.2)

    return entries


def populate_link_status(apps, *stuff):
    SchemeAccountEntry = apps.get_model("ubiquity", "SchemeAccountEntry")

    pending_task_count = 0
    sql_offset = 0
    sql_limit = TASK_SIZE
    pks_to_process = True
    wallet_only_status = ubiquity.models.AccountLinkStatus["WALLET_ONLY"]
    while pks_to_process:
        task_id = str(uuid4())
        pks_to_process = get_wallet_only_entries(SchemeAccountEntry, sql_offset, sql_limit)

        if pks_to_process:
            pending_task_count += 1
            sql_offset += TASK_SIZE
            sql_limit += TASK_SIZE
            retry_redis("set", task_id)
            retry_celery(task_id, pks_to_process, status=wallet_only_status)

    logging.warning(
        f"Finished creating {pending_task_count} async tasks for wallet only cards, moving on to non wallet only cards..."
    )

    task_count = 0
    sql_offset = 0
    sql_limit = TASK_SIZE
    pks_to_process = True
    while pks_to_process:
        task_id = str(uuid4())
        entries = get_non_wallet_only_entries(SchemeAccountEntry, sql_offset, sql_limit)

        pks_to_process = [entry["id"] for entry in entries]
        status_mapping = {entry["id"]: entry["scheme_account__status"] for entry in entries}

        if pks_to_process:
            task_count += 1
            sql_offset += TASK_SIZE
            sql_limit += TASK_SIZE
            retry_redis("set", task_id)
            retry_celery(task_id, pks_to_process, status_mapping=status_mapping)

    if task_count:
        logging.warning(
            f"Finished creating {task_count} async tasks for non wallet only cards, waiting till completion..."
        )
        wait_for_tasks_to_finish()


class Migration(migrations.Migration):
    dependencies = [
        ("ubiquity", "0015_schemeaccountentry_link_status"),
        ("scheme", "0109_alter_schemeaccountcredentialanswer_unique_together_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="schemeaccountentry",
            name="link_status",
            field=models.IntegerField(
                choices=[
                    (0, "Pending"),
                    (1, "Active"),
                    (403, "Invalid credentials"),
                    (432, "Invalid mfa"),
                    (530, "End site down"),
                    (531, "IP blocked"),
                    (532, "Tripped captcha"),
                    (5, "Please check your scheme account login details."),
                    (434, "Account locked on end site"),
                    (429, "Cannot connect, too many retries"),
                    (503, "Too many balance requests running"),
                    (520, "An unknown error has occurred"),
                    (9, "Midas unavailable"),
                    (10, "Wallet only card"),
                    (404, "Agent does not exist on midas"),
                    (533, "Password expired"),
                    (900, "Join"),
                    (444, "No user currently found"),
                    (536, "Error with the configuration or it was not possible to retrieve"),
                    (535, "Request was not sent"),
                    (445, "Account already exists"),
                    (537, "Service connection error"),
                    (401, "Failed validation"),
                    (406, "Pre-registered card"),
                    (446, "Update failed. Delete and re-add card."),
                    (204, "Pending manual check."),
                    (436, "Invalid card_number"),
                    (437, "You can only Link one card per day."),
                    (438, "Unknown Card number"),
                    (439, "General Error such as incorrect user details"),
                    (441, "Join in progress"),
                    (538, "A system error occurred during join"),
                    (447, "The scheme has requested this account should be deleted"),
                    (442, "Asynchronous join in progress"),
                    (443, "Asynchronous registration in progress"),
                    (901, "Enrol Failed"),
                    (902, "Ghost Card Registration Failed"),
                    (ubiquity.models.AccountLinkStatus["JOIN_FAILED"], "JoinFailed"),
                    (ubiquity.models.AccountLinkStatus["AUTHORISATION_FAILED"], "AuthorisationFailed"),
                    (1001, "Add and Auth pending"),
                    (2001, "Auth pending"),
                ],
                default=ubiquity.models.AccountLinkStatus["PENDING"],
            ),
        ),
        # data population, do not need a reverse as the field will be removed if we un-migrate
        migrations.RunPython(populate_link_status),
    ]
