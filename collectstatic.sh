#!/bin/bash
set -ue -o pipefail
pip install -r collect-static-requirements.txt
python manage.py collectstatic --noinput
