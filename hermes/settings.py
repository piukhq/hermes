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
DEBUG = env_var("HERMES_DEBUG", True)

CSRF_TRUSTED_ORIGINS = [
    ".chingrewards.com",
]

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
    "dev.api.chingrewards.com",
    "staging.api.chingrewards.com",
    "api.chingrewards.com",
    "dev.docs.loyaltyangels.local",
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
    'colorful',
    'mail_templated',
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

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 8,
        }
    },
    {
        'NAME': 'user.password_validators.NumericValidator',
    },
    {
        'NAME': 'user.password_validators.UpperCaseCharacterValidator',
    },
    {
        'NAME': 'user.password_validators.LowerCaseCharacterValidator',
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

HASH_ID_SALT = '95429791eee6a6e12d11a5a23d920969f7b1a94d'

MIDAS_URL = env_var('MIDAS_URL', 'http://dev.midas.loyaltyangels.local')
LETHE_URL = env_var('LETHE_URL', 'http://dev.lethe.loyaltyangels.local')
HECATE_URL = env_var('HECATE_URL', 'http://dev.hecate.loyaltyangels.local')
METIS_URL = env_var('METIS_URL', 'http://dev.metis.loyaltyangels.local')

FACEBOOK_CLIENT_SECRET = env_var('FACEBOOK_CLIENT_SECRET', '5da7b80e9e0e25d24097515eb7d506da')

TWITTER_CONSUMER_KEY = env_var('TWITTER_CONSUMER_KEY', 'XhCHpBxJg4YdM5raN2z2GoyAR')
TWITTER_CONSUMER_SECRET = env_var('TWITTER_CONSUMER_SECRET', 'aLnsRBVGrDxdy0oOFbA7pQtjJgzPhrCyLfrcjANkCMqktlV3m5')
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
            'host': env_var('GRAYLOG_HOST'),
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

SWAGGER_BASE_PATH = env_var('SWAGGER_BASE_PATH')
if SWAGGER_BASE_PATH:
    SWAGGER_SETTINGS['base_path'] = SWAGGER_BASE_PATH


SILENCED_SYSTEM_CHECKS = ["urls.W002", ]
if env_var('HERMES_NO_DB_TEST', False):
    # If you want to use this for fast tests in your test class inherit from:
    # from django.test import SimpleTestCase
    TEST_RUNNER = 'hermes.runners.DBLessTestRunner'

FILE_UPLOAD_PERMISSIONS = 0o755

# EMAIL SETTINGS
EMAIL_HOST = "mail.bink.com"
EMAIL_PORT = 587
EMAIL_HOST_USER = "noreply@bink.com"
EMAIL_HOST_PASSWORD = "Gibbon^egg^Change^^"
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False

# Barclays BINs, to be removed when Barclays is supported.
BARCLAYS_BINS = ['543979', '492828', '492827', '492826', '485859', '465823', '452757', '425710', '492829', '464859',
                 '675911', '557062', '557061', '556677', '554988', '554987', '554397', '554201', '554112', '552140',
                 '550619', '550566', '550534', '550005', '548041', '547676', '545186', '540002', '536386', '531214',
                 '530127', '526500', '518776', '518625', '512635', '670502', '492999', '492998', '492997', '492996',
                 '492995', '492994', '492993', '492992', '492991', '492990', '492989', '492988', '492987', '492986',
                 '492985', '492984', '492983', '492982', '492981', '492980', '492979', '492978', '492977', '492976',
                 '492975', '492974', '492973', '492972', '492971', '492970', '492966', '492960', '492959', '492958',
                 '492957', '492956', '492955', '492954', '492953', '492952', '492951', '492950', '492949', '492948',
                 '492947', '492946', '492945', '492944', '492943', '492942', '492941', '492940', '492939', '492938',
                 '492937', '492936', '492935', '492934', '492933', '492932', '492931', '492930', '492929', '492928',
                 '492927', '492926', '492925', '492924', '492923', '492922', '492921', '492920', '492919', '492918',
                 '492917', '492916', '492915', '492914', '492913', '492912', '492910', '492909', '492908', '492907',
                 '492906', '492905', '492904', '492903', '492902', '492901', '492900', '491750', '491749', '491748',
                 '489055', '489054', '487027', '486496', '486485', '486484', '486459', '486451', '486446', '486416',
                 '486404', '486403', '484499', '484498', '484420', '484419', '475149', '474535', '471567', '471566',
                 '471565', '471532', '465923', '465922', '465921', '465911', '465902', '465901', '465867', '465866',
                 '465865', '465864', '465863', '465862', '465861', '465860', '465859', '465858', '462747', '461250',
                 '459898', '459897', '459896', '459885', '459884', '459883', '459881', '459880', '459879', '456725',
                 '453979', '453978', '449355', '447318', '432168', '430532', '429595', '427700', '426525', '426501',
                 '425757', '416022', '416013', '412996', '412995', '412993', '412992', '412991', '412282', '412280',
                 '409402', '409401', '409400', '409026', '409025', '409024', '409023', '408368', '408367', '405068',
                 '403584', '402152', '402148', '402147', '400115', '424564', '557843', '556107', '543247', '541770',
                 '539616', '530129', '530128', '530126', '530125', '530124', '530123', '530122', '530121', '530120',
                 '523065', '520665', '518109', '517240', '517239', '517238', '517237', '517236', '517235', '517234',
                 '517233', '439314', '530831', '426510']