FROM ghcr.io/binkhq/python:3.11
ARG PIP_INDEX_URL
ARG APP_NAME
ARG APP_VERSION
WORKDIR /app
RUN pip install --no-cache ${APP_NAME}==$(echo ${APP_VERSION} | cut -c 2-)
ADD hermes/wsgi.py .
ADD manage.py .

ENTRYPOINT [ "/app/entrypoint.sh" ]
CMD [ "gunicorn", "--workers=2", "--error-logfile=-", "--access-logfile=-", \
    "--logger-class=hermes.reporting.CustomGunicornLogger", \
    "--bind=0.0.0.0:9000", "wsgi" ]
