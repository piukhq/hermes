import os
import sys

import django
from message_lib import QueueParams

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hermes.settings")


def run_receiver():
    # Django setting module needs to be initialised before these import can happen
    from django.conf import settings

    from api_messaging.message_broker import AngeliaReceivingService
    from api_messaging.route import on_message_received

    AngeliaReceivingService(
        rabbitmq_dsn=settings.RABBIT_DSN,
        queue_params=QueueParams(
            queue_name=settings.ANGELIA_QUEUE_NAME,
            exchange_name=f"{settings.ANGELIA_QUEUE_NAME}-exchange",
            routing_key=settings.ANGELIA_QUEUE_ROUTING_KEY,
        ),
        callback=on_message_received,
    ).run()


django.setup(set_prefix=False)
run_receiver()
