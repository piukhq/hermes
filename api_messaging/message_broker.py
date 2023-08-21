from enum import Enum
from typing import TYPE_CHECKING

from django.conf import settings
from message_lib import QueueParams
from message_lib.consumer import AbstractMessageConsumer
from message_lib.producer import MessageProducer

if TYPE_CHECKING:
    from collections.abc import Callable

    from kombu import Message
    from loguru import Logger


class ProducerQueues(Enum):
    MIDAS = settings.MIDAS_QUEUE_NAME
    WAREHOUSE = settings.WAREHOUSE_QUEUE_NAME


sending_service = MessageProducer(
    rabbitmq_dsn=settings.RABBIT_DSN,
    queues_name_and_params={
        ProducerQueues.MIDAS.name: QueueParams(
            queue_name=ProducerQueues.MIDAS.value,
            routing_key=ProducerQueues.MIDAS.value,
            exchange_name=f"{ProducerQueues.MIDAS.value}_exchange",
            exchange_type="direct",
            use_deadletter=False,
        ),
        ProducerQueues.WAREHOUSE.name: QueueParams(
            queue_name=ProducerQueues.WAREHOUSE.value,
            routing_key=ProducerQueues.WAREHOUSE.value,
            exchange_name=f"{ProducerQueues.WAREHOUSE.value}_exchange",
            exchange_type="direct",
            use_deadletter=False,
        ),
    },
)


class AngeliaReceivingService(AbstractMessageConsumer):
    def __init__(
        self,
        rabbitmq_dsn: str,
        queue_params: QueueParams,
        callback: "Callable[[dict, type[Message]], None]",
        custom_log: "Logger | None" = None,
    ):
        super().__init__(rabbitmq_dsn, queue_params, custom_log)
        self._callback = callback

    def on_message(self, body: dict, message: "type[Message]") -> None:
        self._callback(body, message)
