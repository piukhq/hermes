FROM python:3.6

WORKDIR /app
ADD . .

RUN pip install -r /app/requirements.txt && pip install uwsgi && \
    apt update && apt -y install openssl