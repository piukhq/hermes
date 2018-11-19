import os

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hermes.settings')

app = Celery('async_midas')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks(['ubiquity.tasks'])
