import os

from celery import Celery
from django.conf import settings
from kombu import Exchange, Queue

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hermes.settings")

app = Celery("async_tasks")
dead_letter_queue_option = {
    "x-dead-letter-exchange": "ubiquity-async-midas",
    "x-dead-letter-routing-key": "ubiquity-async-midas",
}

"""
******* Warning *******
do not change any parameter in dead letter options above or below especially the
message_ttl etc.  This also applies to other Queues set up in the same way.

If you do Celery will not write to the Queue if it already been created on the server
and the parameters are not an exact match.

If you need to do change the Queue parameter the existing Queue could be deleted just before roll out
or better still set up another dead-letter queue under a new name.
Make sure it is linked like this example to write to the non-delayed processing Queue. After deployment
the old dead-letter Queue may be deleted.   The new dead-letter queue name must replace the old one check
and update where necessary the celery default queue config in settings and the app.conf.task_routes set up
below

"""
app.conf.task_queues = (
    Queue(
        "delayed-70-ubiquity-async-midas",
        exchange=Exchange("ubiquity-async-midas", type="direct"),
        routing_key="ubiquity-async-midas",
        message_ttl=0.07,
        queue_arguments=dead_letter_queue_option,
    ),
)
app.conf.update(
    result_extended=True,
    broker_connection_retry_on_startup=True,
)

app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks(
    [
        "ubiquity.tasks",
        "payment_card.tasks",
        "periodic_retry.tasks",
        "hermes.vop_tasks.tasks",
        "history.tasks",
        "periodic_corrections.tasks",
        "scheme.tasks",
        "scheme.migrations.0109_alter_schemeaccountcredentialanswer_unique_together_and_more",
        "ubiquity.migrations.0016_alter_schemeaccountentry_link_status",
        "ubiquity.migrations.0018_migrate_pll_data",
        "scripts.tasks.file_script_tasks",
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
