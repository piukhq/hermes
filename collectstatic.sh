#!/bin/bash
set -ue -o pipefail
mkdir -p /root/.ssh
echo $DEPLOY_KEY | base64 -d > /root/.ssh/id_rsa
chmod 600 /root/.ssh/id_rsa
ssh-keyscan git.bink.com > /root/.ssh/known_hosts
pip install pipenv
pipenv install --system --deploy --ignore-pipfile
pipenv run python manage.py collectstatic --noinput
