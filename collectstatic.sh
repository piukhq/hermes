#!/bin/bash
set -ue -o pipefail
pip install pipenv
pipenv install --system --deploy --ignore-pipfile
python manage.py collectstatic --noinput
