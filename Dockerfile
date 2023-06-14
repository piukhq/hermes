FROM ghcr.io/binkhq/python:3.11-pipenv

WORKDIR /app
ADD . .

RUN pipenv install --system --deploy --ignore-pipfile

ENTRYPOINT [ "/app/entrypoint.sh" ]
CMD [ "gunicorn", "--error-logfile=-", "--access-logfile=-", \
        "--bind=0.0.0.0:9000", "--logger-class=hermes.reporting.CustomGunicornLogger", \
        "hermes.wsgi" ]
