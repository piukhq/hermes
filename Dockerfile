FROM python:3.7-alpine

WORKDIR /app
ADD . .
ARG DEPLOY_KEY
RUN apk add --no-cache --virtual build \
      openssh-client \
      git \
      libffi-dev \
      zlib-dev \
      build-base && \
    apk add --no-cache \
      jpeg-dev \
      postgresql-dev && \
    mkdir -p /root/.ssh && \
    echo $DEPLOY_KEY | base64 -d > /root/.ssh/id_rsa && chmod 600 /root/.ssh/id_rsa && \
    ssh-keyscan git.bink.com > /root/.ssh/known_hosts && \
    pip install gunicorn "pipenv==2018.11.26" && \
    pipenv install --system --deploy --ignore-pipfile && \
    apk del --no-cache build && rm -rf /root/.ssh

CMD ["/usr/local/bin/gunicorn", "-c", "gunicorn.py", "hermes.wsgi"]
