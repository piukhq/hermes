from kombu import Connection, Exchange, Producer, Queue
import atexit


class MessagingService:

    def __init__(self, user, password, queue_name, host, port):
        self.conn = None
        self.producer = None
        atexit.register(self.cleanup)
        self.user = user
        self.password = password
        self.host = host
        self.port = port
        self.queue_name = queue_name
        self.exchange = Exchange(f'{self.queue_name}_exchange', type='direct', durable=True)
        self.queue = Queue(self.queue_name, exchange=self.exchange, routing_key=queue_name)
        self.connect()

    def connect(self):
        if self.conn:
            self.close()
        self.conn = Connection(f"amqp://{self.password}:{self.user}@{self.host}:{self.port}/")
        self.producer = Producer(exchange=self.exchange,
                                 channel=self.conn.channel(),
                                 routing_key=self.queue_name, serializer='json')
        self.queue.maybe_bind(self.conn)
        self.queue.declare()

    def _pub(self, kwargs):
        self.producer.publish(**kwargs)

    def send(self, notice: dict):
        kwargs = {
            'body': notice,
            'headers': {
                'X-version': '1.0',
                'X-content-type': 'application/json'
            }
        }

        print(f'Hermes to Daedalus-update: {kwargs}')
        try:
            self._pub(kwargs)
        except Exception as e:
            print(f'Exception on connecting to Message Broker - time out? {e} retry send')
            self.close()
            self.connect()
            self._pub(kwargs)

    def cleanup(self):
        self.close()

    def close(self):
        if self.conn:
            self.conn.release()
            self.conn = None
