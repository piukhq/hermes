#!/bin/sh

set -e

echo "Waiting for Linkerd to be up"

linkerd-await

echo "Collecting statics"
python ./manage.py collectstatic --noinput

echo "Starting gunicorn"
exec "$@"
