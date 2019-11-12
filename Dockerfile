FROM python:3.7-alpine

WORKDIR /app
ADD . .

RUN apk add --no-cache --virtual build \
      git \
      libffi-dev \
      zlib-dev \
      build-base && \
    apk add --no-cache \
      su-exec \
      jpeg-dev \
      libc-dev \
      binutils \
      postgresql-dev && \
    pip install gunicorn pipenv && \
    pipenv install --system --deploy --ignore-pipfile && \
    apk del --no-cache build
