FROM ghcr.io/binkhq/python@sha256:7b4642b7c42997643e75df6371c5f4b74138183e25192d5cb0d1d99218c1adc2

WORKDIR /app
ADD . .

RUN pipenv install --system --deploy --ignore-pipfile

ENTRYPOINT [ "/app/entrypoint.sh" ]
CMD [ "gunicorn", "--workers=2", "--threads=2", "--error-logfile=-", \
                  "--access-logfile=-", "--bind=0.0.0.0:9000", "hermes.wsgi" ]
