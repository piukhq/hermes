FROM python:3.6

ADD . /app

RUN pip install -r /app/requirements.txt && pip install uwsgi && \
    apt update && apt -y install openssl

