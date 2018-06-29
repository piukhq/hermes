#!/bin/bash
set -ue -o pipefail
pip install -r requirements.txt
python manage.py collectstatic --noinput
