"""
Django settings for hermes project.

Generated by 'django-admin startproject' using Django 1.8.4.

For more information on this file, see
https://docs.djangoproject.com/en/1.8/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.8/ref/settings/
"""

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
import os
import raven
from environment import env_var, read_env
import dj_database_url
import sys

read_env()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.8/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = '*is3^%seh_2=sgc$8dw+vcd)5cwrecvy%cxiv69^q8hz3q%=fo'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env_var("HERMES_DEBUG", False)

ALLOWED_HOSTS = [
    "127.0.0.1",
    ".chingrewards.com"
]
CORS_ALLOW_CREDENTIALS = True
CORS_ORIGIN_ALLOW_ALL = False
CORS_ORIGIN_WHITELIST = (
    "127.0.0.1",
    "0.0.0.0:8001",
    "staging.chingweb.chingrewards.com",
    "local.chingweb.chingrewards.com",
    "dev.chingweb.loyaltyangels.local",
    "local.chingweb.chingrewards.com:8000",
)


# Application definition

INSTALLED_APPS = (
    'raven.contrib.django.raven_compat',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.admin',
    'rest_framework',
    'rest_framework_swagger',
    'corsheaders',
    'user',
    'scheme',
    'payment_card',
    'order',
)

MIDDLEWARE_CLASSES = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',  # 'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.auth.middleware.SessionAuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
)

ROOT_URLCONF = 'hermes.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'user.authentication.JwtAuthentication',
    ),
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
    )
}


WSGI_APPLICATION = 'hermes.wsgi.application'


# Database
# https://docs.djangoproject.com/en/1.8/ref/settings/#databases


DATABASES = {
    'default': dj_database_url.parse(
        env_var("HERMES_DATABASE_URL", "postgres://postgres@localhost:5432/hermes"))
}


# Internationalization
# https://docs.djangoproject.com/en/1.8/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True

AUTHENTICATION_BACKENDS = (
    'hermes.email_auth.EmailBackend',
)

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.8/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, "static/")

MEDIA_ROOT = os.path.join(BASE_DIR, 'media/')
MEDIA_URL = env_var("HERMES_MEDIA_URL", '/media/')

AUTH_USER_MODEL = 'user.CustomUser'

LOCAL_AES_KEY = 'OLNnJPTcsdBXi1UqMBp2ZibUF3C7vQ'
AES_KEY = '6gZW4ARFINh4DR1uIzn12l7Mh1UF982L'

SERVICE_API_KEY = 'F616CE5C88744DD52DB628FAD8B3D'

MIDAS_URL = env_var('MIDAS_URL', 'http://dev.midas.loyaltyangels.local')

FACEBOOK_CLIENT_SECRET = env_var('FACEBOOK_CLIENT_SECRET', '5da7b80e9e0e25d24097515eb7d506da')

TWITTER_CONSUMER_KEY = env_var('TWITTER_CONSUMER_KEY', '8p69caPi2Q1YTMKsgJRhi5UZI')
TWITTER_CONSUMER_SECRET = env_var('TWITTER_CONSUMER_SECRET', '7WIpFgSykKWQ4ofj5FNPqpEQgYvNbMWiMJdOCkhfxDwnwjNbM9')
TWITTER_CALLBACK_URL = env_var('TWITTER_CALLBACK_URL', 'http://local.chingweb.chingrewards.com:8000/')

TOKEN_SECRET = "8vA/fjVA83(n05LWh7R4'$3dWmVCU"

LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'root': {
        'level': 'WARNING',
        'handlers': ['sentry'],
    },
    'formatters': {
        'verbose': {
            'format': '%(levelname)s %(asctime)s %(module)s '
                      '%(process)d %(thread)d %(message)s'
        },
    },
    'handlers': {
        'sentry': {
            'level': 'ERROR',
            'class': 'raven.contrib.django.raven_compat.handlers.SentryHandler',
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose'
        },
        'gelf': {
            'class': 'graypy.GELFHandler',
            'host': '192.168.1.53',
            'port': 12201,
        },
    },
    'loggers': {
        'django.db.backends': {
            'level': 'ERROR',
            'handlers': ['console'],
            'propagate': False,
        },
        'raven': {
            'level': 'DEBUG',
            'handlers': ['console'],
            'propagate': False,
        },
        'sentry.errors': {
            'level': 'DEBUG',
            'handlers': ['console'],
            'propagate': False,
        },
        'graylog': {
            # mail_admins will only accept ERROR and higher
            'handlers': ['gelf'],
            'level': 'DEBUG',
        },
    },
}

DEBUG_PROPAGATE_EXCEPTIONS = env_var('HERMES_PROPAGATE_EXCEPTIONS', False)

TESTING = (len(sys.argv) > 1 and sys.argv[1] == 'test') or sys.argv[0][-7:] == 'py.test'
LOCAL = env_var('HERMES_LOCAL', False)

HERMES_SENTRY_DNS = env_var('HERMES_SENTRY_DNS', None)
if not any([TESTING, LOCAL]) and HERMES_SENTRY_DNS:
    RAVEN_CONFIG = {
        'dsn': HERMES_SENTRY_DNS,
        # If you are using git, you can also automatically configure the
        # release based on the git info.
        'release': raven.fetch_git_sha(BASE_DIR),
    }

SWAGGER_SETTINGS = {
    'api_version': '1',
    'info': {
        'contact': 'Paul Batty',
        'description': 'Loyalty Angels REST API for registering users and loyalty rewards schemes. '
                       '<br>'
                       'All calls to the the API endpoints require an authorization token obtained '
                       'by registering through the Registration endpoint. '
                       '<br>'
                       'An Authorization token in the form "Token eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXV..." is '
                       'required in the header. ',
        'title': 'Loyalty Angels registrations service - Hermes',
    },
}

if env_var('HERMES_NO_DB_TEST', False):
    # If you want to use this for fast tests in your test class inherit from:
    # from django.test import SimpleTestCase
    TEST_RUNNER = 'hermes.runners.DBLessTestRunner'
