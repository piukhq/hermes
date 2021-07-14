import logging
import os
import django


logger = logging.getLogger(__name__)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hermes.settings")

TIME_OUT = 4
RABBIT_PASSWORD = "guest"
RABBIT_USER = "guest"
RABBIT_HOST = "127.0.0.1"
RABBIT_PORT = 5672


def imports():
    from django.conf import settings
    from route import on_message_received
    from api_messaging.message_broker import ReceivingService
    ReceivingService(
            user=settings.RABBIT_USER,
            password=settings.RABBIT_PASSWORD,
            host=settings.RABBIT_HOST,
            port=settings.RABBIT_PORT,
            queue_name="from_api2",
            heartbeat=settings.TIME_OUT * 3,
            timeout=settings.TIME_OUT,
            callbacks=[on_message_received],
            on_time_out=on_time_out
        )


def on_time_out():
    pass


django.setup(set_prefix=False)

imports()
