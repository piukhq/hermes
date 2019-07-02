import os

from celery import Celery

from hermes.settings import RETRY_PERIOD

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hermes.settings')

app = Celery('async_midas')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks(['ubiquity.tasks'])

app.conf.beat_schedule = {
    'retry_tasks': {
        'task': 'hermes.tasks.retry_tasks',
        'schedule': int(RETRY_PERIOD),
        'args': ()
    }
}

# Send retry tasks to a separate queue instead of default ubiquity queue
app.conf.task_routes = {'retry_tasks': {'queue': 'retry_tasks'}}
