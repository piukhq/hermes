import os

from celery import Celery
from celery.schedules import crontab
from django.conf import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hermes.settings")

app = Celery("async_tasks")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks(
    [
        "ubiquity.tasks",
        "payment_card.tasks",
        "periodic_retry.tasks",
        "hermes.vop_tasks.tasks",
        "history.tasks",
        "notification.tasks",
        "periodic_corrections.tasks",
        "scheme.migrations.0109_alter_schemeaccountcredentialanswer_unique_together_and_more",
        "ubiquity.migrations.0016_alter_schemeaccountentry_link_status",
        "ubiquity.migrations.0018_migrate_pll_data",
    ]
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
    "generate_notification_file": {
        "task": "notification.tasks.notification_file",
        "schedule": crontab(minute=0, hour=settings.NOTIFICATION_RUN_TIME),
        "args": (False,),
    },
    "periodic_corrections_tasks": {
        "task": "periodic_corrections.tasks.retain_pending_payments",
        "schedule": int(settings.PERIODIC_CORRECTIONS_PERIOD),
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
