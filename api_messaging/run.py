import logging
import os
import django

from api_messaging.message_broker import ReceivingService
from api_messaging.route import route_message


logger = logging.getLogger(__name__)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hermes.settings")

TIME_OUT = 4
RABBIT_PASSWORD = "guest"
RABBIT_USER = "guest"
RABBIT_HOST = "127.0.0.1"
RABBIT_PORT = 5672

django.setup(set_prefix=False)


def on_message_recieved(body, message):
    logger.info("API 2 message received")
    # print(f"got message: {message}  body: {body} headers: {message.headers}")
    try:
        success = route_message(message.headers, body)
    except RuntimeError:
        if not message.acknowledged:
            message.reject()
    if not message.acknowledged:
        if success:
            message.ack()
        else:
            message.requeue()


def on_time_out():
    pass
