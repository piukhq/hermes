FROM binkhq/python:3.7

WORKDIR /app
ADD . .

RUN apt-get update && apt-get -y install git && \
    pip install --no-cache-dir pipenv==2018.11.26 gunicorn && \
    pipenv install --system --deploy --ignore-pipfile && \
    pip uninstall -y pipenv && apt-get -y autoremove git && \
    apt-get clean

CMD [ "gunicorn", "--workers=2", "--threads=2", "--error-logfile=-", \
                  "--access-logfile=-", "--bind=0.0.0.0:9000", "hermes.wsgi" ]
