# Hermes

[![build status](https://gitlab.com/hellobink/Olympus/hermes/badges/master/build.svg)](https://gitlab.com/hellobink/Olympus/hermes/commits/master) [![coverage report](https://gitlab.com/hellobink/Olympus/hermes/badges/master/coverage.svg)](https://gitlab.com/hellobink/Olympus/hermes/commits/master)

*From the minds of Andrew Kenyon and Ben Olsen, (Sponsored by Paul Batty and Mick Latham Inc.),
 we give you Hermes....a self contained user registration module. Incorporating all your payment and loyalty card registration too...*

## Components
 * Django 1.9
 * Postgresql 9.1+

## Installation (Ubuntu Linux)
 * Install Python 3 virtual environment and Postgres dependencies required for C bindings to PsycoPG2 driver
   * sudo apt-get install python3-pip python3-dev libpq-dev postgresql postgresql-contrib
   * sudo pip3 install virtualenv
   * virtualenv ~/.virtualenvs/hermes
 * Install Python dependencies (Or setup PyCharm to use a Docker based Python)
   * source  ~/.virtualenvs/hermes/bin/activate
   * cd ~/code_dir/hermes
   * pip install -r requirements.txt
 * Install Docker and docker-compose
 * Setup environment specific settings
   * Create .env file in project root
   * Add entry for DB connection: HERMES_DATABASE_URL="postgres://postgres@localhost:5432/postgres"
   * DB name can be changed however you need to tell docker by setting environment var POSTGRES_USER="*DB-NAME*"
 * Start postgres
   * cd app_dir
   * docker-compose up
 * Run DB Migrations - ./manage.py migrate
 * Run application - ./manage.py runserver
 * __Creating an entity relationship diagram__
   * Note: Do not check any of these changes in please; this is a guide only.
   * sudo apt-get install graphviz libgraphviz-dev pkg-config
   * Add 'django_extensions' to INSTALLED_APPS in settings.py.
   * pip install django-extensions pydotplus pygraphviz
   * Run python manage.py graph_models -a -o hermes_models.png

## Installation (MacOS)
 * Install Python 3 virtual environment and Postgres dependencies required for C bindings to PsycoPG2 driver
     * Install Xcode from the Mac App Store
     * Install [Python 3](https://www.python.org/downloads/mac-osx/)
     * Install [`homebrew`](https://brew.sh) if not already installed
     * Install correct Postgres version but do not run from homebrew: `brew install postgres@9.5`
 * Install requirements for librabbitmq
   * `brew install autoconf automake pkg-config libtool`
 * Install Python dependencies (Or setup PyCharm to use a Docker based Python)
   * source  ~/.virtualenvs/hermes/bin/activate
   * cd ~/code_dir/hermes
   * pip install -r requirements.txt
 * Install Azure-CLI for keyvault access (or alternatively you are able to use a local secrets file)
   * `brew install azure-cli`
   * Then: `az login` will take you to a browser to sign into Azure.
   * When trying to run an application in Pycharm it may abort when trying to load secrets
   - if you have this issue especially after just rebooting run az login before running PyCharm
 * Install Docker and Postgres
     * Download and install [Docker](https://docs.docker.com/docker-for-mac/install/)
     * Pull Docker Postgres: `docker pull postgres:9.5`
 * Start Postgres
     * `docker run --name hermes-postgres -p 127.0.0.1:5432:5432 -d postgres`
 * Create Hermes Database
     * `psql -h localhost -U postgres`
     * `create database hermes;`
 * Run DB Migrations - ./manage.py migrate
 * Run application - ./manage.py runserver


## Docker Configuration

### Environment Variables

- `DATABASE_IP`
  - String Value, usually an FQDN or IP Address
- `DATABASE_PORT`
  - String Value, port for Postgres, usually 5432
- `DATABASE_USER`
  - String Value, username to use for auth with Postgres
- `DATABASE_PASS`
  - String Value, password to use for auth with Postgres
- `DATABASE_NAME`
  - String Value, name of database within Postgres
- `DEBUG`
  - `True` = Enable Debug Features
  - `False` = Disable Debug Features
- `MEDIA_URL`
  - String Value, URL to serve media on, usually https://<fqdn>/media
- `MIDAS_URL`
  - String Value, URL to access Midas
- `HECATE_URL`
  - String Value, URL to access Hecate
- `LETHE_URL`
  - String Value, URL to access Lethe
- `METIS_URL`
  - String Value, URL to access Metis
- `ENVIRONMENT_NAME`
  - String Value, text of django admin environment message
- `ENVIRONMENT_COLOR`
  - String Value, hex value of django admin environment message background colour
- `VAULT_URL`
  - String Value, URL access to Azure keyvault

## Running the Hermes Locally in Pycharm

In Pycharm set up the following run configs ie select Edit Configurations :

Note: In all settings add environment variables:

    Environmental Variables: PYTHONUNBUFFERED=1;DJANGO_SETTINGS_MODULE=hermes.settings
    Python Interpreter:  Python in hermes virtual env
    Working Directory: top directory of hermes app eg .../pycharm_projects/hermes
and refer to the correct python interpreter ie in the virtualenv.

Under **Django Server** create config:

    hermes api 1.x/admin
        host: 127:0:0:1  port: 8000

Under Python create configs:

    celery
        Module Name: celery
        Parameters: -A hermes worker --loglevel=INFO --concurrency=1 -Q ubiquity-async-midas,record-history,retry-tasks


    celery beat:
        Module Name: celery
        Parameters: -A hermes beat --loglevel=INFO

    api2:
        script path: /Users/mmarsh/PycharmProjects/hermes/api_messaging/run.py

To start the select each config above on the drop down and click on either the
run or debug icon. You should then have under the run or debug window all 4
services running.

Note celery will consume 3 task queues ubiquity-async-midas, record-history, retry-tasks
If you have installed manage version of rabbitMQ the queues can be seen on

    http://127.0.0.1:15672/#/queues

An additional non-celery related Queue "from_angelia" can be monitored. This Queue as the name implies
contains messages from Angelia to the hermes back end "api2" application
