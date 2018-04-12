#!/bin/bash
set -ue -o pipefail
pip install -r /app/requirements.txt
python manage.py collectstatic --noinput

