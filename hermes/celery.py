import os

from celery import Celery

from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hermes.settings')

app = Celery('async_midas')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks(['ubiquity.tasks', 'payment_card.tasks'])

app.conf.beat_schedule = {
    'retry_tasks': {
        'task': 'hermes.tasks.retry_tasks',
        'schedule': int(settings.RETRY_PERIOD),
        'args': ()
    },
    'expired_payment_void_task': {
        'task': 'payment_card.tasks.expired_payment_void_task',
        'schedule': int(settings.PAYMENT_EXPIRY_CHECK_INTERVAL),
        'args': ()
    }
}

# Send retry tasks to a separate queue instead of default ubiquity queue
app.conf.task_routes = {
    'retry_tasks': {'queue': 'retry_tasks'},
    'expired_payment_void_task': {'queue': 'retry_tasks'}
}
