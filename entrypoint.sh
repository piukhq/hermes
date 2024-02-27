#!/bin/sh

set -e

echo "Collecting statics"
python ./manage.py collectstatic --noinput

echo "Starting gunicorn"
exec "$@"
