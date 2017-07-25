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
