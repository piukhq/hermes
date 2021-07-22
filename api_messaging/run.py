import logging
import os
import django

from hermes.settings import RABBIT_DSN

logger = logging.getLogger(__name__)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hermes.settings")


def run_receiver():
    # Django setting module needs to be initialised before these import can happen
    from django.conf import settings
    from route import on_message_received
    from api_messaging.message_broker import ReceivingService
    ReceivingService(
            dsn=RABBIT_DSN,
            queue_name="from_angelia",
            heartbeat=settings.TIME_OUT * 3,
            timeout=settings.TIME_OUT,
            callbacks=[on_message_received],
            on_time_out=on_time_out
        )


def on_time_out():
    pass


django.setup(set_prefix=False)
run_receiver()
