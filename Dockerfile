FROM python:3.6

WORKDIR /app
ADD . .

RUN pip install -r /app/requirements.txt && pip install uwsgi

ENTRYPOINT /usr/local/bin/uwsgi --logger ignore file:/dev/null --log-route ignore healthz --http :9000 --chdir /app --wsgi-file hermes/wsgi.py --master --threads "2" --processes "4"
