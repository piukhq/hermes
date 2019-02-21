FROM python:3.6-alpine

WORKDIR /app
ADD . .

RUN apk add --no-cache --virtual build \
      git \
      libffi-dev \
      build-base && \
    apk add --no-cache \
      su-exec \
      postgresql-dev && \
    adduser -D hermes && \
    pip install gunicorn pipenv && \
    pipenv install --system --deploy --ignore-pipfile && \
    apk del --no-cache build

CMD ["/sbin/su-exec","hermes","/usr/local/bin/gunicorn","-w 4","-b 0.0.0.0:9000","hermes.wsgi"]
