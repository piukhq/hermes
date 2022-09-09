FROM ghcr.io/binkhq/python:3.9-pipenv

WORKDIR /app
ADD . .

RUN pip install --no-cache pipenv
RUN pipenv install --system --deploy --ignore-pipfile

ENTRYPOINT [ "/app/entrypoint.sh" ]
CMD [ "gunicorn", "--workers=2", "--threads=2", "--error-logfile=-", \
                  "--access-logfile=-", "--bind=0.0.0.0:9000", "hermes.wsgi" ]
