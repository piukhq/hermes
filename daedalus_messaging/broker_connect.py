from kombu import Connection, Exchange, Queue

media_exchange = Exchange('media', 'direct', durable=True)
video_queue = Queue('video', exchange=media_exchange, routing_key='video')



# connections
with Connection('amqp://guest:guest@localhost//') as conn:

    # produce
    producer = conn.Producer(serializer='json')
    producer.publish({'name': '/tmp/lolcat1.avi', 'size': 1301013},
                      exchange=media_exchange, routing_key='video',
                      declare=[video_queue])



class MessagingService:

    def __init__(self, user, password, queue, host, port):
        self.user = user
        self.password = password
        self.queue = queue
        self.host = host
        self.port = port
        self.conn = Connection(f"ampq://{password}:{user}@{host}:{port}/")

    def connect(self):
        self.conn = stomp.Connection12([(self.host, self.port)])
        self.conn.start()
        self.conn.connect(self.user, self.password, wait=True)
        if not self.conn:
            raise Exception
        print(f"Connected to Artemis {self.user} {self.password} q={self.queue}")

    def send(self, notice: dict):

        body_json = json.dumps(notice)
        headers = {
            'destination-type': 'ANYCAST',
            'X-version': '1.0',
            'X-content-type': 'application/json'
        }

        print(f'Hermes to Daedalus-update: {body_json} headers: {headers} q={self.queue}')
        try:
            self.conn.send(body=body_json, destination=self.queue, headers=headers)
        except Exception as e:
            print(f'Exception on connecting to Artemis Broker - time out? {e} retry send')
            self.connect()
            self.conn.send(body=body_json, destination=self.queue, headers=headers)

    def close(self):
        self.conn.disconnect()
