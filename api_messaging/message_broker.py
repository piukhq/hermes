import atexit
import logging
import socket
from time import sleep
from typing import cast

from django.conf import settings
from kombu import Connection, Consumer, Exchange, Producer, Queue

logger = logging.getLogger(__name__)


class BaseMessaging:
    def __init__(self, dsn: str):
        self.conn = None
        self.producer = {}
        atexit.register(self.close)
        self.dsn = dsn
        self.connect()

        # Check connection on startup
        err_msg = "Failed to connect to messaging service. Please check the configuration."
        if self.conn:
            try:
                self.conn.connect()
                self.conn.release()
            except ConnectionRefusedError:
                logger.exception(err_msg)
                raise
        else:
            raise ConnectionError(err_msg)

    def connect(self):
        if self.conn:
            self.close()
        self.conn = Connection(self.dsn)

    def close(self):
        if self.conn:
            self.conn.release()
            self.conn = None


class SendingService(BaseMessaging):
    def __init__(self, dsn: str, log_to: logging = None):
        super().__init__(dsn)
        self.conn = None
        self.producer = {}
        self.queue = {}
        self.exchange = {}
        self.connect()
        self.consumer = None
        if log_to is None:
            self.logger = logging.getLogger("messaging")
        else:
            self.logger = log_to

    def _pub(self, queue_name: str, kwargs: dict):
        producer = self.producer.get(queue_name, None)
        if producer is None:
            exchange = self.exchange.get(queue_name, None)
            if exchange is None:
                self.exchange[queue_name] = Exchange(f"{queue_name}_exchange", type="direct", durable=True)
            self.queue[queue_name] = Queue(queue_name, exchange=self.exchange[queue_name], routing_key=queue_name)
            self.queue[queue_name].maybe_bind(self.conn)
            self.queue[queue_name].declare()

            self.producer[queue_name] = producer = Producer(
                exchange=self.exchange[queue_name],
                channel=self.conn.channel(),
                routing_key=queue_name,
                serializer="json",
            )
        producer.publish(**kwargs)

    def _pub_retry(self, queue_name: str, kwargs: dict) -> None:
        last_exc: Exception | None = None
        for i in range(settings.PUBLISH_MAX_RETRIES):
            try:
                sleep(i * settings.PUBLISH_RETRY_BACKOFF_FACTOR)
                self.close()
                self.connect()
                self._pub(queue_name, kwargs)
                break
            except Exception as e:
                last_exc = e
                self.logger.warning("Exception '{exc!r}' on connecting to Message Broker, trying again", exc=e)

        # The logic in an 'else' clause when applied to a for loop will be executed only if the loop completed
        # naturally without exiting prematurely. In this case it will be executed only if 'break' was never called.
        else:
            self.logger.exception("Failed to send message, max retries exceeded.", exc_info=last_exc)
            raise cast(Exception, last_exc)

    def send(self, message: dict, headers: dict, queue_name: str):
        headers["destination-type"] = "ANYCAST"
        message = {"body": message, "headers": headers}

        try:
            self._pub(queue_name, message)
        except Exception:
            self._pub_retry(queue_name, message)

    def close(self):
        if self.conn:
            self.conn.release()
            self.conn = None

        self.producer = {}
        self.queue = {}
        self.exchange = {}


class ReceivingService(BaseMessaging):
    def __init__(
        self,
        dsn: str,
        queue_name: str,
        callbacks: list,
        on_time_out=None,
        heartbeat: int = 10,
        timeout: int = 2,
        continue_exceptions=None,
        log_to: logging = None,
    ):
        super().__init__(dsn)

        self.queue_name = queue_name
        self.connect()
        self.exchange = Exchange(f"{self.queue_name}_exchange", type="direct", durable=True)

        dlx_name = self.exchange.name + "_dlx"
        self.deadletter_exchange = Exchange(
            name=dlx_name,
            type="fanout",
            durable=True,
            delivery_mode="persistent",
            auto_delete=False,
        )
        self.deadletter_queue = Queue(
            name=self.deadletter_exchange.name + "_queue",
            exchange=self.deadletter_exchange,
            durable=True,
            auto_delete=False,
        )
        self.deadletter_queue(self.conn).declare()
        self.queue = Queue(
            self.queue_name,
            exchange=self.exchange,
            routing_key=queue_name,
            queue_arguments={
                "x-dead-letter-exchange": dlx_name,
                "x-dead-letter-routing-key": "deadletter",
            },
        )
        self.consumer = None
        self.heartbeat = heartbeat
        self.timeout = timeout
        self.callbacks = callbacks
        self.on_time_out = on_time_out
        if log_to is None:
            self.logger = logging.getLogger("messaging")
        else:
            self.logger = log_to
        logging.getLogger("amqp").setLevel(logging.WARNING)
        if continue_exceptions is not None:
            self.continue_exceptions = continue_exceptions
        else:
            self.continue_exceptions = ConnectionError
        self.dispatch_loop()

    def setup_consumer(self):
        if not self.conn:
            self.connect()
        self.consumer = Consumer(self.conn, queues=self.queue, callbacks=self.callbacks, accept=["application/json"])
        self.consumer.consume()

    def dispatch_loop(self):
        while True:
            if not self.consumer or not self.conn:
                self.setup_consumer()
            try:
                while True:
                    try:
                        self.conn.drain_events(timeout=self.timeout)
                    except socket.timeout:
                        self.conn.heartbeat_check()
                        if self.on_time_out is not None:
                            self.on_time_out()
            except self.continue_exceptions as e:
                self.logger.debug(f"Message Queue Reading Loop Error: {e}")
                sleep(1)
                self.close()
