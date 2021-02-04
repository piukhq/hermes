import os

from celery import Celery
from django.conf import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hermes.settings")

app = Celery("async_tasks")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks(
    ["ubiquity.tasks", "payment_card.tasks", "periodic_retry.tasks", "hermes.vop_tasks.tasks", "history.tasks"]
)

app.conf.beat_schedule = {
    "retry_tasks": {
        "task": "hermes.tasks.retry_tasks",
        "schedule": int(settings.RETRY_PERIOD),
        "args": (),
    },
    "expired_payment_void_task": {
        "task": "payment_card.tasks.expired_payment_void_task",
        "schedule": int(settings.PAYMENT_EXPIRY_CHECK_INTERVAL),
        "args": (),
    },
    "retry_metis_request_tasks": {
        "task": "periodic_retry.tasks.retry_metis_request_tasks",
        "schedule": int(settings.RETRY_PERIOD),
        "args": (),
    },
}

# Send retry and history tasks to a separate queue instead of default ubiquity queue
app.conf.task_routes = {
    "history.tasks.record_history": {"queue": "record-history"},
    "history.tasks.bulk_record_history": {"queue": "record-history"},
    "retry_tasks": {"queue": "retry-tasks"},
    "expired_payment_void_task": {"queue": "retry-tasks"},
    "retry_metis_request_tasks": {"queue": "retry-tasks"},
}
