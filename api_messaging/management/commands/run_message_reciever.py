from django.core.management.base import BaseCommand
from django.conf import settings

from api_messaging.message_broker import ReceivingService
from api_messaging.run import on_message_recieved, on_time_out


class Command(BaseCommand):
    help = "Run receiver to process messages from Angelia."

    def handle(self, *args, **kwargs):
        self.stdout.write('Running receiver service.')
        ReceivingService(
            user=settings.RABBIT_USER,
            password=settings.RABBIT_PASSWORD,
            host=settings.RABBIT_HOST,
            port=settings.RABBIT_PORT,
            queue_name="from_api2",
            heartbeat=settings.TIME_OUT * 3,
            timeout=settings.TIME_OUT,
            callbacks=[on_message_recieved],
            on_time_out=on_time_out
        )
