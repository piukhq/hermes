FROM binkhq/python:3.7

WORKDIR /app
ADD . .
ARG DEPLOY_KEY

RUN apt-get update && apt-get -y install openssh-client git && \
    pip install --no-cache-dir pipenv==2018.11.26 gunicorn && \
    mkdir -p /root/.ssh && \
    echo $DEPLOY_KEY | base64 -d > /root/.ssh/id_rsa && chmod 600 /root/.ssh/id_rsa && \
    ssh-keyscan git.bink.com > /root/.ssh/known_hosts && \
    pipenv install --system --deploy --ignore-pipfile && \
    pip uninstall -y pipenv && apt-get -y autoremove openssh-client git && \
    apt-get clean && rm -rf /var/lib/apt/lists /root/.ssh

CMD [ "gunicorn", "--workers=2", "--threads=2", "--error-logfile=-", \
                  "--access-logfile=-", "--bind=0.0.0.0:9000", "hermes.wsgi" ]
