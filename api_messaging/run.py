import os
import django

from api_messaging.message_broker import ReceivingService

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hermes.settings")

TIME_OUT = 4
RABBIT_PASSWORD = "guest"
RABBIT_USER = "guest"
RABBIT_HOST = "127.0.0.1"
RABBIT_PORT = 5672

django.setup(set_prefix=False)


def on_message_recieved(body, message):
    print(f"got message: {message}  body: {body} headers: {message.headers}")
    # call process and return success or not
    success = True
    if not message.acknowledged:
        if success:
            message.ack()
        else:
            message.requeue()


def on_time_out():
    pass


ReceivingService(
    user=RABBIT_USER,
    password=RABBIT_PASSWORD,
    host=RABBIT_HOST,
    port=RABBIT_PORT,
    queue_name="from_api2",
    heartbeat=TIME_OUT * 3,
    timeout=TIME_OUT,
    callbacks=[on_message_recieved],
    on_time_out=on_time_out
)
