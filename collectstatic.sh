#!/bin/bash
set -ue -o pipefail
pip install $(egrep '^Django==|^django-colorful==|^djangorestframework==' requirements.txt)
python manage.py collectstatic --noinput
