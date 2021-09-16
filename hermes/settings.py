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
import sys
from collections import namedtuple
from enum import Enum

import sentry_sdk
from sentry_sdk.integrations import celery, django
from sentry_sdk.integrations.redis import RedisIntegration

from environment import env_var, read_env
from hermes.sentry import _make_celery_event_processor, _make_django_event_processor, strip_sensitive_data
from hermes.version import __version__
from redis import ConnectionPool as Redis_ConnectionPool
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.celery import CeleryIntegration

read_env()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.8/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "*is3^%seh_2=sgc$8dw+vcd)5cwrecvy%cxiv69^q8hz3q%=fo"

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env_var("HERMES_DEBUG", True)

CSRF_TRUSTED_ORIGINS = [
    "127.0.0.1",
    ".bink.com",
]

ALLOWED_HOSTS = ["*"]
CORS_ALLOW_CREDENTIALS = True
CORS_ORIGIN_ALLOW_ALL = True

# Application definition
LOCAL_APPS = (
    "sso",
    "user",
    "scheme",
    "payment_card",
    "order",
    "ubiquity",
    "history",
    "periodic_retry",
    "magic_link",
    "scripts",
    "prometheus.apps.PrometheusPusherConfig",
    "api_messaging"
)

INSTALLED_APPS = (
    "django_admin_env_notice",
    "sso.apps.AADAdminConfig",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "mozilla_django_oidc",
    "rest_framework",
    "corsheaders",
    "colorful",
    "mail_templated",
    "anymail",
    "storages",
    "rangefilter",
    "django_prometheus",
    *LOCAL_APPS,
)

# add 'hermes.middleware.QueryDebug', to top of middleware list to see in debug sql queries in response header
# add 'hermes.middleware.TimedRequest', to top of middleware list to see request times in response header
MIDDLEWARE = (
    "prometheus.middleware.CustomPrometheusBeforeMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",  # 'django.middleware.csrf.CsrfViewMiddleware',
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "dictfilter.django.middleware.DictFilterMiddleware",
    "hermes.middleware.AcceptVersion",
    "history.middleware.HistoryRequestMiddleware",
    "prometheus.middleware.CustomPrometheusAfterMiddleware",
)

ROOT_URLCONF = "hermes.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django_admin_env_notice.context_processors.from_settings",
            ],
        },
    },
]

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {"NAME": "user.password_validators.NumericValidator"},
    {"NAME": "user.password_validators.UpperCaseCharacterValidator"},
    {"NAME": "user.password_validators.LowerCaseCharacterValidator"},
]


class Version(str, Enum):
    v1_0 = "1.0"
    v1_1 = "1.1"
    v1_2 = "1.2"
    v1_3 = "1.3"

    def __gt__(self, other):
        major, minor = map(int, self.value.split("."))
        other_major, other_minor = map(int, other.value.split("."))

        if major == other_major:
            return minor > other_minor
        else:
            return major > other_major

    def __lt__(self, other):
        major, minor = map(int, self.value.split("."))
        other_major, other_minor = map(int, other.value.split("."))

        if major == other_major:
            return minor < other_minor
        else:
            return major < other_major


DEFAULT_API_VERSION = env_var("DEFAULT_API_VERSION", max(Version).value)

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_AUTHENTICATION_CLASSES": ("user.authentication.JwtAuthentication",),
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
    "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.AcceptHeaderVersioning",
    "DEFAULT_VERSION": DEFAULT_API_VERSION,
    "VERSION_PARAM": "v",
    "EXCEPTION_HANDLER": "ubiquity.exceptions.custom_exception_handler",
}

WSGI_APPLICATION = "hermes.wsgi.application"

APPEND_SLASH = False

# Database
# https://docs.djangoproject.com/en/1.8/ref/settings/#databases


DATABASES = {
    "default": {
        # "ENGINE": "django.db.backends.postgresql_psycopg2",
        "ENGINE": "hermes.traced_db_wrapper",
        "NAME": env_var("HERMES_DATABASE_NAME", "hermes"),
        "USER": env_var("HERMES_DATABASE_USER", "postgres"),
        "PASSWORD": env_var("HERMES_DATABASE_PASS"),
        "HOST": env_var("HERMES_DATABASE_HOST", "postgres"),
        "PORT": env_var("HERMES_DATABASE_PORT", "5432"),
    }
}

# Internationalization
# https://docs.djangoproject.com/en/1.8/topics/i18n/

LANGUAGE_CODE = "en-gb"

TIME_ZONE = "Europe/London"

USE_I18N = True

USE_L10N = True

USE_TZ = True

BINK_CLIENT_ID = "MKd3FfDGBi1CIUQwtahmPap64lneCa2R6GvVWKg6dNg4w9Jnpd"
BINK_BUNDLE_ID = "com.bink.wallet"


AUTHENTICATION_BACKENDS = [
    "sso.auth.SSOAuthBackend",
    "hermes.email_auth.EmailBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.8/howto/static-files/

NO_AZURE_STORAGE = env_var("NO_AZURE_STORAGE", True)

if not NO_AZURE_STORAGE:
    DEFAULT_FILE_STORAGE = "storages.backends.azure_storage.AzureStorage"
    AZURE_CONTAINER = env_var("HERMES_BLOB_STORAGE_CONTAINER", "media/hermes")
    HERMES_CUSTOM_DOMAIN = env_var("HERMES_CUSTOM_DOMAIN", "https://api.dev.gb.bink.com")
    AZURE_CONNECTION_STRING = env_var("HERMES_BLOB_STORAGE_DSN", "")
    # For generating image urls with a custom domain
    CONTENT_URL = f"{HERMES_CUSTOM_DOMAIN}/content"
    AZURE_CUSTOM_CONNECTION_STRING = f"{AZURE_CONNECTION_STRING};BlobEndpoint={CONTENT_URL}"
    MAGIC_LINK_TEMPLATE = 'email/magic_link_email.txt'


MEDIA_URL = env_var("HERMES_MEDIA_URL", "/media/")
MEDIA_ROOT = os.path.join(BASE_DIR, "media/")

STATIC_URL = env_var("HERMES_STATIC_URL", "/admin/static/")
STATIC_ROOT = "/tmp/static/"

AUTH_USER_MODEL = "user.CustomUser"

SERVICE_API_KEY = "F616CE5C88744DD52DB628FAD8B3D"
SERVICE_API_METRICS_BUNDLE = "internal_service"

HASH_ID_SALT = "95429791eee6a6e12d11a5a23d920969f7b1a94d"

MIDAS_URL = env_var("MIDAS_URL", "http://dev.midas.loyaltyangels.local")
LETHE_URL = env_var("LETHE_URL", "http://dev.lethe.loyaltyangels.local")
HECATE_URL = env_var("HECATE_URL", "http://dev.hecate.loyaltyangels.local")
METIS_URL = env_var("METIS_URL", "http://dev.metis.loyaltyangels.local")
HADES_URL = env_var("HADES_URL", "http://dev.hades.loyaltyangels.local")
MNEMOSYNE_URL = env_var("MNEMOSYNE_URL", None)
MY360_SCHEME_URL = "https://mygravity.co/my360/"
MY360_SCHEME_API_URL = "https://rewards.api.mygravity.co/v3/reward_scheme/{}/schemes"

FACEBOOK_CLIENT_SECRET = env_var("FACEBOOK_CLIENT_SECRET", "5da7b80e9e0e25d24097515eb7d506da")

TWITTER_CONSUMER_KEY = env_var("TWITTER_CONSUMER_KEY", "XhCHpBxJg4YdM5raN2z2GoyAR")
TWITTER_CONSUMER_SECRET = env_var("TWITTER_CONSUMER_SECRET", "aLnsRBVGrDxdy0oOFbA7pQtjJgzPhrCyLfrcjANkCMqktlV3m5")
TWITTER_CALLBACK_URL = env_var("TWITTER_CALLBACK_URL", "http://local.chingweb.chingrewards.com:8000/")

APPLE_APP_ID = env_var("APPLE_APP_ID", "com.bink.wallet")
APPLE_CLIENT_SECRET = env_var("APPLE_CLIENT_SECRET", "")
APPLE_KEY_ID = env_var("APPLE_KEY_ID", "6H3RLHRVGC")
APPLE_TEAM_ID = env_var("APPLE_TEAM_ID", "HC34M8YE55")

DEBUG_PROPAGATE_EXCEPTIONS = env_var("HERMES_PROPAGATE_EXCEPTIONS", False)

TESTING = (len(sys.argv) > 1 and sys.argv[1] == "test") or any("pytest" in arg for arg in sys.argv)
INIT_RUNTIME_APPS = TESTING is False and not any(x in sys.argv for x in ["migrate", "makemigrations", "collectstatic"])
LOCAL = env_var("HERMES_LOCAL", False)

ROOT_LOG_LEVEL = env_var("ROOT_LOG_LEVEL", "WARNING")
MASTER_LOG_LEVEL = env_var("MASTER_LOG_LEVEL", "DEBUG")
UBIQUITY_LOG_LEVEL = env_var("UBIQUITY_LOG_LEVEL", "DEBUG")
PROMETHEUS_LOG_LEVEL = env_var("PROMETHEUS_LOG_LEVEL", "INFO")
QUERY_LOG_LEVEL = env_var("QUERY_LOG_LEVEL", "CRITICAL")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "%(asctime)s :: %(name)s :: %(levelname)s :: %(message)s"},
    },
    "handlers": {
        "console": {
            "level": MASTER_LOG_LEVEL,
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "filters": {
        "require_debug_true": {"()": "django.utils.log.RequireDebugTrue"},
    },
    "loggers": {
        "": {
            "level": ROOT_LOG_LEVEL,
            "handlers": ["console"],
        },
        "django.db.backends": {
            "filters": ["require_debug_true"],
            "level": QUERY_LOG_LEVEL,
            "handlers": ["console"],
            "propagate": False,
        },
        **{
            app: {
                "level": MASTER_LOG_LEVEL,
                "handlers": ["console"],
                "propagate": False,
            }
            for app in LOCAL_APPS
        },
        # Place any custom loggers per app below this to override above
        "ubiquity": {
            "level": UBIQUITY_LOG_LEVEL,
            "handlers": ["console"],
            "propagate": False,
        },
        "hermes": {
            "level": MASTER_LOG_LEVEL,
            "handlers": ["console"],
            "propagate": False,
        },
        "prometheus": {
            "level": PROMETHEUS_LOG_LEVEL,
            "handlers": ["console"],
            "propagate": False,
        },
    },
}

HERMES_SENTRY_DSN = env_var("HERMES_SENTRY_DSN", None)
HERMES_SENTRY_ENV = env_var("HERMES_SENTRY_ENV", None)
SENTRY_SAMPLE_RATE = float(env_var("SENTRY_SAMPLE_RATE", "0.0"))
if HERMES_SENTRY_DSN:
    sentry_sdk.init(
        dsn=HERMES_SENTRY_DSN,
        environment=HERMES_SENTRY_ENV,
        release=__version__,
        integrations=[DjangoIntegration(transaction_style="url", middleware_spans=False),
                      RedisIntegration(),
                      CeleryIntegration()],
        traces_sample_rate=SENTRY_SAMPLE_RATE,
        send_default_pii=False,
        before_send=strip_sensitive_data,
    )
    # Monkey patching sentry integrations to allow scrubbing of sensitive data in performance traces
    celery._make_event_processor = _make_celery_event_processor
    django._make_event_processor = _make_django_event_processor

ANYMAIL = {
    "MAILGUN_API_KEY": "b09950929bd21cbece22c22b2115736d-e5e67e3e-068f44cc",
    "MAILGUN_SENDER_DOMAIN": "bink.com",
    "MAILGUN_API_URL": "https://api.eu.mailgun.net/v3",
}
EMAIL_BACKEND = "anymail.backends.mailgun.EmailBackend"
DEFAULT_FROM_EMAIL = "Bink Support <support@bink.com>"
DEFAULT_MAGIC_LINK_FROM_EMAIL = "{external_name}@bink.com"

SILENCED_SYSTEM_CHECKS = ["urls.W002"]
if env_var("HERMES_NO_DB_TEST", False):
    # If you want to use this for fast tests in your test class inherit from:
    # from django.test import SimpleTestCase
    TEST_RUNNER = "hermes.runners.DBLessTestRunner"

FILE_UPLOAD_PERMISSIONS = 0o755

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

ENVIRONMENT_NAME = env_var("ENVIRONMENT_NAME", None)
ENVIRONMENT_COLOR = env_var("ENVIRONMENT_COLOR", None)

# how many seconds leeway is allowed to account for clock skew in JWT validation
CLOCK_SKEW_LEEWAY = env_var("CLOCK_SKEW_LEEWAY", 180)

REDIS_HOST = env_var("REDIS_HOST", "localhost")
REDIS_PASSWORD = env_var("REDIS_PASSWORD", "")
REDIS_PORT = env_var("REDIS_PORT", 6379)
REDIS_DB = env_var("REDIS_DB", 1)
REDIS_URL = env_var('REDIS_URL',
                    f'redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}')

REDIS_API_CACHE_DB = env_var("REDIS_API_CACHE_DB", 2)
REDIS_MPLANS_CACHE_EXPIRY = int(env_var("REDIS_MPLANS_CACHE_EXPIRY", 60 * 60 * 24))  # 60*60*24  # 24 hrs in seconds

REDIS_READ_TIMEOUT = float(env_var("REDIS_READ_TIMEOUT", 0.3))
REDIS_WRITE_TIMEOUT = float(env_var("REDIS_WRITE_TIMEOUT", 20))
REDIS_RETRY_COUNT = 3
REDIS_READ_HEALTH_CHECK_INTERVAL = 1
REDIS_WRITE_HEALTH_CHECK_INTERVAL = 1


REDIS_READ_API_CACHE_POOL = Redis_ConnectionPool.from_url(
    url=REDIS_URL,
    socket_timeout=REDIS_READ_TIMEOUT,
    health_check_interval=REDIS_READ_HEALTH_CHECK_INTERVAL,
)
REDIS_WRITE_API_CACHE_POOL = Redis_ConnectionPool.from_url(
    url=REDIS_URL,
    socket_timeout=REDIS_WRITE_TIMEOUT,
    health_check_interval=REDIS_WRITE_HEALTH_CHECK_INTERVAL,
)

cache_options = {
    "redis": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
        "KEY_PREFIX": "hermes",
    },
    "test": {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
    },
}
CACHES = {
    "default": cache_options["test"] if TESTING else cache_options["redis"],
    "retry_tasks": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient", "MAX_ENTRIES": 10000, "CULL_FREQUENCY": 100},
        "KEY_PREFIX": "hermes-retry-task-",
        "TIMEOUT": None,
    },
}

BALANCE_RENEW_PERIOD = 20 * 60  # 20 minutes

TOKEN_SECRET = "8vA/fjVA83(n05LWh7R4'$3dWmVCU"

USE_INFLUXDB = env_var("USE_INFLUXDB", False)
INFLUX_DB_NAME = env_var("INFLUX_DB_NAME", "active_card_audit")
INFLUX_DB_CONFIG = {
    "host": env_var("INFLUX_HOST", "localhost"),
    "port": int(env_var("INFLUX_PORT", 8086)),
    "username": env_var("INFLUX_USER", ""),
    "password": env_var("INFLUX_PASSWORD", ""),
}

# Celery
CELERY_BROKER_URL = env_var("CELERY_BROKER_URL", "pyamqp://guest@localhost//")
CELERY_TASK_DEFAULT_QUEUE = env_var("CELERY_TASK_DEFAULT_QUEUE", "ubiquity-async-midas")
CELERY_TASK_SERIALIZER = "pickle"
CELERY_ACCEPT_CONTENT = ["pickle", "json"]
CELERY_RESULT_SERIALIZER = "pickle"
CELERY_ENABLE_REMOTE_CONTROL = False

SPREEDLY_BASE_URL = env_var("SPREEDLY_BASE_URL", "")

# Time in seconds for the interval between retry tasks called by celery beats
RETRY_PERIOD = env_var("RETRY_PERIOD", "900")
# Time in seconds for interval of checking if payments have not been updated and require voiding
PAYMENT_EXPIRY_CHECK_INTERVAL = env_var("PAYMENT_EXPIRY_CHECK_INTERVAL", "600")

# Time in seconds of how long is required before a payment is deemed to be expired
PAYMENT_EXPIRY_TIME = env_var("PAYMENT_EXPIRY_TIME", "120")

ATLAS_URL = env_var("ATLAS_URL")

SCHEMES_COLLECTING_METRICS = env_var("SCHEMES_COLLECTING_METRICS", "cooperative").split(",")

BinMatch = namedtuple("BinMatch", "type len value")
BIN_TO_PROVIDER = {
    "visa": [
        BinMatch(type="equal", len=1, value="4"),
    ],
    "amex": [BinMatch(type="equal", len=2, value="34"), BinMatch(type="equal", len=2, value="37")],
    "mastercard": [BinMatch(type="range", len=2, value=(51, 55)), BinMatch(type="range", len=4, value=(2221, 2720))],
}

INTERNAL_SERVICE_BUNDLE = env_var("INTERNAL_SERVICE_BUNDLE", "com.bink.daedalus")
JWT_EXPIRY_TIME = env_var("JWT_EXPIRY_TIME", 600)


VAULT_CONFIG = dict(
    # Hashicorp vault settings for secrets retrieval
    VAULT_URL=env_var("VAULT_URL", "http://localhost:8200"),
    VAULT_TOKEN=env_var("VAULT_TOKEN", "myroot"),
    # SET Signing secrets for JWT authentication
    # For deployment set LOCAL_SECRETS to False and set up Vault envs
    # For local use without Vault Set LOCAL_CHANNEL_SECRETS to False to True
    # and set LOCAL_SECRETS_PATH to your json file. See example_local_secrets.json for format
    # (Do not commit your local_secrets json which might contain real secrets or edit example_local_secrets.json)
    LOCAL_SECRETS=env_var("LOCAL_SECRETS", False),
    LOCAL_SECRETS_PATH=env_var("LOCAL_SECRETS_PATH", "example_local_secrets.json"),
    CHANNEL_VAULT_PATH=env_var("CHANNEL_VAULT_PATH", "/channels"),
    SECRET_KEYS_VAULT_PATH=env_var("SECRET_KEYS_VAULT_PATH", "/secret-keys"),
    AES_KEYS_VAULT_PATH=env_var("AES_KEYS_VAULT_PATH", "/aes-keys"),
    BARCLAYS_SFTP_VAULT_PATH=env_var("BARCLAYS_SFTP_VAULT_PATH", "/barclays-hermes-sftp")
)

CSRF_COOKIE_HTTPONLY = env_var("SECURE_COOKIES", "False")
CSRF_COOKIE_SECURE = env_var("SECURE_COOKIES", "False")
SESSION_COOKIE_HTTPONLY = env_var("SECURE_COOKIES", "False")
SESSION_COOKIE_SECURE = env_var("SECURE_COOKIES", "False")

# OIDC SSO
SSO_OFF = env_var("SSO_OFF", "False")
LOGIN_REDIRECT_URL = "/admin/"
LOGIN_REDIRECT_URL_FAILURE = "/admin/error/403"
OIDC_RP_REPLY_URL = env_var("OIDC_RP_REPLY_URL", "https://api.dev.gb.bink.com/admin/oidc/callback/")
OIDC_AUTHENTICATE_CLASS = "sso.auth.CustomOIDCAuthenticationRequestView"
OIDC_RP_CLIENT_ID = env_var("OIDC_CLIENT_ID", "1a5d83f3-da1f-401c-ac5f-d41c3fa0d9ef")
OIDC_RP_CLIENT_SECRET = env_var("OIDC_CLIENT_SECRET", "-NGSjpWWx_1w-6~.NkIl3lf~DC3Rg-.CMz")
OIDC_RP_SIGN_ALGO = "RS256"
OIDC_OP_JWKS_ENDPOINT = "https://login.microsoftonline.com/a6e2367a-92ea-4e5a-b565-723830bcc095/discovery/v2.0/keys"
OIDC_OP_AUTHORIZATION_ENDPOINT = (
    "https://login.microsoftonline.com/a6e2367a-92ea-4e5a-b565-723830bcc095/oauth2/v2.0/authorize"
)
OIDC_OP_TOKEN_ENDPOINT = "https://login.microsoftonline.com/a6e2367a-92ea-4e5a-b565-723830bcc095/oauth2/v2.0/token"
OIDC_OP_USER_ENDPOINT = "https://graph.microsoft.com/oidc/userinfo"
OIDC_RENEW_ID_TOKEN_EXPIRY_SECONDS = 60 * 30

PROMETHEUS_EXPORT_MIGRATIONS = False
PROMETHEUS_LATENCY_BUCKETS = (.050, .125, .150, .2, .375, .450, .6, .8, 1.0, 2.0, 3.0, 4.0, 6.0, 8.0, 10.0, 12.0,
                              15.0, 20.0, 30.0, float("inf"))
PROMETHEUS_PUSH_GATEWAY = env_var('PROMETHEUS_PUSH_GATEWAY', 'http://localhost:9100')
PROMETHEUS_JOB = "hermes"

ENCRYPTED_VALUES_LENGTH_CONTROL = int(env_var("ENCRYPTED_VALUES_LENGTH_CONTROL", "255"))

# RABBIT
TIME_OUT = env_var("TIMEOUT", 4)
RABBIT_PASSWORD = env_var("RABBIT_PASSWORD", "guest")
RABBIT_USER = env_var("RABBIT_USER", "guest")
RABBIT_HOST = env_var("RABBIT_HOST", "127.0.0.1")
RABBIT_PORT = env_var("RABBIT_PORT", 5672)
RABBIT_DSN = env_var("RABBIT_DSN", f"amqp://{RABBIT_USER}:{RABBIT_PASSWORD}@{RABBIT_HOST}:{RABBIT_PORT}/")

# SFTP DETAILS
SFTP_DIRECTORY = env_var("SFTP_DIRECTORY", "uploads")

# 2 hours
NOTIFICATION_PERIOD = int(env_var("NOTIFICATION_PERIOD", 7200))
NOTIFICATION_ERROR_THRESHOLD = int(env_var("NOTIFICATION_ERROR_THRESHOLD", 5))
# 2 minutes
NOTIFICATION_RETRY_TIMER = int(env_var("NOTIFICATION_RETRY_TIMER", 120))
NOTIFICATION_RUN = env_var("NOTIFICATION_RUN", False)
# Barclays notification file suffix
BARCLAYS_SFTP_FILE_SUFFIX = env_var("BARCLAYS_SFTP_FILE_SUFFIX", "_DTUIL05787")
