#!/bin/sh
echo "Waiting for Linkerd to be up"

counter=1
while true
do
  echo "Attempt ${counter}"
  STATUS=$(curl --connect-timeout 3 --max-time 5 -sL -w "%{http_code}\\n" "http://localhost:4191/ready" -o /dev/null)
  if [ "$STATUS" = "200" ]; then
    echo "Linkerd is up"
    break
  fi

  if [ $counter -gt 6 ]; then
    echo "Linkerd not up, continuing anyway"
    break
  fi

  echo "Linkerd not up, waiting"
  counter=$((counter + 1))
  sleep 3
done

echo "Collecting statics"
python ./manage.py collectstatic --noinput

echo "Starting gunicorn"
exec "$@"
