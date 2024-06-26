"""
Django settings for hermes project.

Generated by 'django-admin startproject' using Django 1.8.4.

For more information on this file, see
https://docs.djangoproject.com/en/1.8/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.8/ref/settings/
"""

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
import logging
import os
import sys
from collections import namedtuple
from enum import Enum

import dj_database_url
import sentry_sdk
from bink_logging_utils import init_loguru_root_sink
from decouple import Choices, config
from redis import ConnectionPool as Redis_ConnectionPool
from sentry_sdk.integrations import celery, django
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.redis import RedisIntegration

from hermes.sentry import _make_celery_event_processor, _make_django_event_processor, strip_sensitive_data
from hermes.utils import ctx
from hermes.version import __version__

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.8/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "*is3^%seh_2=sgc$8dw+vcd)5cwrecvy%cxiv69^q8hz3q%=fo"

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config("HERMES_DEBUG", default=True, cast=bool)

CSRF_TRUSTED_ORIGINS = [
    "http://127.0.0.1",
    "https://*.bink.com",
    "https://*.bink.sh",
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
    "api_messaging",
    "periodic_corrections",
)

INSTALLED_APPS = (
    "django_admin_env_notice",
    "sso.apps_admin.AADAdminConfig",
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
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "dictfilter.django.middleware.DictFilterMiddleware",
    "hermes.middleware.AcceptVersion",
    "hermes.middleware.AzureRef",
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


DEFAULT_API_VERSION = config("DEFAULT_API_VERSION", default=max(Version).value)

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

if config("HERMES_DATABASE_URL", default=None):
    DATABASES = {
        "default": dj_database_url.config(
            env="HERMES_DATABASE_URL",
            conn_max_age=600,
            engine="hermes.traced_db_wrapper",
        )
    }
else:
    DATABASES = {
        "default": {
            # "ENGINE": "django.db.backends.postgresql_psycopg2",
            "ENGINE": "hermes.traced_db_wrapper",
            "NAME": config("HERMES_DATABASE_NAME", default="hermes"),
            "USER": config("HERMES_DATABASE_USER", default="postgres"),
            "PASSWORD": config("HERMES_DATABASE_PASS", default=""),
            "HOST": config("HERMES_DATABASE_HOST", default="postgres"),
            "PORT": config("HERMES_DATABASE_PORT", default="5432"),
        }
    }

# Internationalization
# https://docs.djangoproject.com/en/1.8/topics/i18n/

LANGUAGE_CODE = "en-gb"

TIME_ZONE = "Europe/London"

USE_I18N = True

USE_L10N = True

USE_TZ = True

SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_COOKIE_AGE = config("SESSION_COOKIE_AGE", default=240 * 60, cast=int)

BINK_CLIENT_ID = "MKd3FfDGBi1CIUQwtahmPap64lneCa2R6GvVWKg6dNg4w9Jnpd"
BINK_BUNDLE_ID = "com.bink.wallet"


AUTHENTICATION_BACKENDS = [
    "sso.auth.SSOAuthBackend",
    "hermes.email_auth.EmailBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.8/howto/static-files/

NO_AZURE_STORAGE = config("NO_AZURE_STORAGE", default=True, cast=bool)
UPLOAD_CONTAINER_NAME = config("UPLOAD_CONTAINER_NAME", default="hermes-imports")
ARCHIVE_CONTAINER_NAME = config("ARCHIVE_CONTAINER_NAME", default="hermes-archive")

if not NO_AZURE_STORAGE:
    DEFAULT_FILE_STORAGE = "hermes.storage.CustomAzureStorage"
    AZURE_CONTAINER = config("HERMES_BLOB_STORAGE_CONTAINER", default="media/hermes")
    AZURE_CONNECTION_STRING = config("HERMES_BLOB_STORAGE_DSN", default="")
    # For generating image urls with a custom domain
    MAGIC_LINK_TEMPLATE = "email/magic_link_email.txt"

HERMES_CUSTOM_DOMAIN = config("HERMES_CUSTOM_DOMAIN", default="https://api.dev.gb.bink.com")
CONTENT_URL = f"{HERMES_CUSTOM_DOMAIN}/content/hermes"
MEDIA_URL = config("HERMES_MEDIA_URL", default="/media/")
MEDIA_ROOT = os.path.join(BASE_DIR, "media/")

STATIC_URL = config("HERMES_STATIC_URL", default="/admin/static/")
STATIC_ROOT = config("HERMES_STATIC_ROOT", default="/tmp/static/")

AUTH_USER_MODEL = "user.CustomUser"

SERVICE_API_KEY = "F616CE5C88744DD52DB628FAD8B3D"
SERVICE_API_METRICS_BUNDLE = "internal_service"

HASH_ID_SALT = "95429791eee6a6e12d11a5a23d920969f7b1a94d"

MIDAS_URL = config("MIDAS_URL", default="http://dev.midas.loyaltyangels.local")
LETHE_URL = config("LETHE_URL", default="http://dev.lethe.loyaltyangels.local")
HECATE_URL = config("HECATE_URL", default="http://dev.hecate.loyaltyangels.local")
METIS_URL = config("METIS_URL", default="http://dev.metis.loyaltyangels.local")
HADES_URL = config("HADES_URL", default="http://dev.hades.loyaltyangels.local")
MY360_SCHEME_URL = "https://mygravity.co/my360/"
MY360_SCHEME_API_URL = "https://rewards.api.mygravity.co/v3/reward_scheme/{}/schemes"

MIDAS_QUEUE_NAME = config("MIDAS_QUEUE_NAME", default="loyalty-request")

ANGELIA_QUEUE_NAME = config("ANGELIA_QUEUE_NAME", default="angelia-hermes-bridge")
ANGELIA_QUEUE_ROUTING_KEY = config("ANGELIA_QUEUE_ROUTING_KEY", default="angelia")

APPLE_APP_ID = config("APPLE_APP_ID", default="com.bink.wallet")
APPLE_CLIENT_SECRET = config("APPLE_CLIENT_SECRET", default="")
APPLE_KEY_ID = config("APPLE_KEY_ID", default="6H3RLHRVGC")
APPLE_TEAM_ID = config("APPLE_TEAM_ID", default="HC34M8YE55")

DEBUG_PROPAGATE_EXCEPTIONS = config("HERMES_PROPAGATE_EXCEPTIONS", default=False, cast=bool)

TESTING = (len(sys.argv) > 1 and sys.argv[1] == "test") or any("pytest" in arg for arg in sys.argv)
INIT_RUNTIME_APPS = TESTING is False and not any(x in sys.argv for x in ["migrate", "makemigrations", "collectstatic"])

LOG_LEVEL_CHOICES = Choices(["DEBUG", "INFO", "WARN", "WARNING", "ERROR", "EXCEPTION", "CRITICAL"])

JSON_LOGGING = config("JSON_LOGGING", default=True, cast=bool)
ROOT_LOG_LEVEL = config("ROOT_LOG_LEVEL", default="WARNING", cast=LOG_LEVEL_CHOICES)
MASTER_LOG_LEVEL = config("MASTER_LOG_LEVEL", default="DEBUG", cast=LOG_LEVEL_CHOICES)
UBIQUITY_LOG_LEVEL = config("UBIQUITY_LOG_LEVEL", default="DEBUG", cast=LOG_LEVEL_CHOICES)
PROMETHEUS_LOG_LEVEL = config("PROMETHEUS_LOG_LEVEL", default="INFO", cast=LOG_LEVEL_CHOICES)
QUERY_LOG_LEVEL = config("QUERY_LOG_LEVEL", default="CRITICAL", cast=LOG_LEVEL_CHOICES)


def azure_ref_patcher(record: logging.LogRecord):
    if ctx.x_azure_ref:
        record["extra"].update({"x-azure-ref": ctx.x_azure_ref})


init_loguru_root_sink(
    json_logging=JSON_LOGGING, sink_log_level=MASTER_LOG_LEVEL, show_pid=True, custom_patcher=azure_ref_patcher
)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "()": "hermes.reporting.InterceptHandler",
        }
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
        "messaging": {
            "level": MASTER_LOG_LEVEL,
            "handlers": ["console"],
            "propagate": False,
        },
    },
}


HERMES_SENTRY_DSN = config("HERMES_SENTRY_DSN", default=None)
HERMES_SENTRY_ENV = config("HERMES_SENTRY_ENV", default=None)
SENTRY_SAMPLE_RATE = config("SENTRY_SAMPLE_RATE", default=0.0, cast=float)
if HERMES_SENTRY_DSN:
    sentry_sdk.init(
        dsn=HERMES_SENTRY_DSN,
        environment=HERMES_SENTRY_ENV,
        release=__version__,
        integrations=[
            DjangoIntegration(transaction_style="url", middleware_spans=False),
            RedisIntegration(),
            CeleryIntegration(),
        ],
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
if config("HERMES_NO_DB_TEST", default=False, cast=bool):
    # If you want to use this for fast tests in your test class inherit from:
    # from django.test import SimpleTestCase
    TEST_RUNNER = "hermes.runners.DBLessTestRunner"

FILE_UPLOAD_PERMISSIONS = 0o755

# Barclays BINs, to be removed when Barclays is supported.
BARCLAYS_BINS = [
    "543979",
    "492828",
    "492827",
    "492826",
    "485859",
    "465823",
    "452757",
    "425710",
    "492829",
    "464859",
    "675911",
    "557062",
    "557061",
    "556677",
    "554988",
    "554987",
    "554397",
    "554201",
    "554112",
    "552140",
    "550619",
    "550566",
    "550534",
    "550005",
    "548041",
    "547676",
    "545186",
    "540002",
    "536386",
    "531214",
    "530127",
    "526500",
    "518776",
    "518625",
    "512635",
    "670502",
    "492999",
    "492998",
    "492997",
    "492996",
    "492995",
    "492994",
    "492993",
    "492992",
    "492991",
    "492990",
    "492989",
    "492988",
    "492987",
    "492986",
    "492985",
    "492984",
    "492983",
    "492982",
    "492981",
    "492980",
    "492979",
    "492978",
    "492977",
    "492976",
    "492975",
    "492974",
    "492973",
    "492972",
    "492971",
    "492970",
    "492966",
    "492960",
    "492959",
    "492958",
    "492957",
    "492956",
    "492955",
    "492954",
    "492953",
    "492952",
    "492951",
    "492950",
    "492949",
    "492948",
    "492947",
    "492946",
    "492945",
    "492944",
    "492943",
    "492942",
    "492941",
    "492940",
    "492939",
    "492938",
    "492937",
    "492936",
    "492935",
    "492934",
    "492933",
    "492932",
    "492931",
    "492930",
    "492929",
    "492928",
    "492927",
    "492926",
    "492925",
    "492924",
    "492923",
    "492922",
    "492921",
    "492920",
    "492919",
    "492918",
    "492917",
    "492916",
    "492915",
    "492914",
    "492913",
    "492912",
    "492910",
    "492909",
    "492908",
    "492907",
    "492906",
    "492905",
    "492904",
    "492903",
    "492902",
    "492901",
    "492900",
    "491750",
    "491749",
    "491748",
    "489055",
    "489054",
    "487027",
    "486496",
    "486485",
    "486484",
    "486459",
    "486451",
    "486446",
    "486416",
    "486404",
    "486403",
    "484499",
    "484498",
    "484420",
    "484419",
    "475149",
    "474535",
    "471567",
    "471566",
    "471565",
    "471532",
    "465923",
    "465922",
    "465921",
    "465911",
    "465902",
    "465901",
    "465867",
    "465866",
    "465865",
    "465864",
    "465863",
    "465862",
    "465861",
    "465860",
    "465859",
    "465858",
    "462747",
    "461250",
    "459898",
    "459897",
    "459896",
    "459885",
    "459884",
    "459883",
    "459881",
    "459880",
    "459879",
    "456725",
    "453979",
    "453978",
    "449355",
    "447318",
    "432168",
    "430532",
    "429595",
    "427700",
    "426525",
    "426501",
    "425757",
    "416022",
    "416013",
    "412996",
    "412995",
    "412993",
    "412992",
    "412991",
    "412282",
    "412280",
    "409402",
    "409401",
    "409400",
    "409026",
    "409025",
    "409024",
    "409023",
    "408368",
    "408367",
    "405068",
    "403584",
    "402152",
    "402148",
    "402147",
    "400115",
    "424564",
    "557843",
    "556107",
    "543247",
    "541770",
    "539616",
    "530129",
    "530128",
    "530126",
    "530125",
    "530124",
    "530123",
    "530122",
    "530121",
    "530120",
    "523065",
    "520665",
    "518109",
    "517240",
    "517239",
    "517238",
    "517237",
    "517236",
    "517235",
    "517234",
    "517233",
    "439314",
    "530831",
    "426510",
]

ENVIRONMENT_NAME = config("ENVIRONMENT_NAME", default=None)
ENVIRONMENT_COLOR = config("ENVIRONMENT_COLOR", default=None)

# how many seconds leeway is allowed to account for clock skew in JWT validation
CLOCK_SKEW_LEEWAY = config("CLOCK_SKEW_LEEWAY", default=180, cast=int)

REDIS_URL = config("REDIS_URL", default="redis://localhost:6379/1")
REDIS_MPLANS_CACHE_EXPIRY = config(
    "REDIS_MPLANS_CACHE_EXPIRY",
    default=60 * 60 * 24,  # 60*60*24 is 24 hrs in seconds
    cast=int,
)
REDIS_MPLANS_CACHE_PREFIX = "m_plans"


REDIS_READ_TIMEOUT = config("REDIS_READ_TIMEOUT", default=0.3, cast=float)
REDIS_WRITE_TIMEOUT = config("REDIS_WRITE_TIMEOUT", default=20.0, cast=float)
REDIS_RETRY_COUNT = 3
REDIS_READ_HEALTH_CHECK_INTERVAL = 1
REDIS_WRITE_HEALTH_CHECK_INTERVAL = 1

REDIS_API_CACHE_SCAN_BATCH_SIZE = config("REDIS_API_CACHE_SCAN_BATCH_SIZE", default=5_000, cast=int)
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

TOKEN_SECRET = "8vA/fjVA83(n05LWh7R4'$3dWmVCU"

USE_INFLUXDB = config("USE_INFLUXDB", default=False, cast=bool)
INFLUX_DB_NAME = config("INFLUX_DB_NAME", "default=active_card_audit")
INFLUX_DB_CONFIG = {
    "host": config("INFLUX_HOST", default="localhost"),
    "port": config("INFLUX_PORT", default=8086, cast=int),
    "username": config("INFLUX_USER", default=""),
    "password": config("INFLUX_PASSWORD", default=""),
}

# RABBIT
TIME_OUT = config("TIMEOUT", default=4, cast=int)
RABBIT_DSN = config("RABBIT_DSN", default="amqp://guest:guest@localhost/")
PUBLISH_MAX_RETRIES = config("PUBLISH_MAX_RETRIES", 3, cast=int)
PUBLISH_RETRY_BACKOFF_FACTOR = config("PUBLISH_RETRY_BACKOFF_FACTOR", 0.25, cast=float)

# Celery
CELERY_BROKER_URL = RABBIT_DSN
CELERY_TASK_DEFAULT_QUEUE = config("CELERY_TASK_DEFAULT_QUEUE", default="delayed-70-ubiquity-async-midas")
CELERY_WORKER_ENABLE_REMOTE_CONTROL = False
CELERY_TASK_SERIALIZER = "pickle"
CELERY_ACCEPT_CONTENT = ["pickle", "json"]
CELERY_RESULT_SERIALIZER = "pickle"
CELERY_RESULT_BACKEND = REDIS_URL

SPREEDLY_BASE_URL = config("SPREEDLY_BASE_URL", default="")  # "https://core.spreedly.com/v1"

# Time in seconds for periodic corrections to be called by celery beats
PERIODIC_CORRECTIONS_PERIOD = config("PERIODIC_CORRECTIONS_PERIOD", default=600, cast=int)
RETAIN_FROM_MINUTES = config("RETAIN_FROM_MINUTES", default=-720, cast=int)
RETAIN_TO_MINUTES = config("RETAIN_TO_MINUTES", default=-5, cast=int)

# Time in seconds for the interval between retry tasks called by celery beats
RETRY_PERIOD = config("RETRY_PERIOD", default=900, cast=int)
# Time in seconds for interval of checking if payments have not been updated and require voiding
PAYMENT_EXPIRY_CHECK_INTERVAL = config("PAYMENT_EXPIRY_CHECK_INTERVAL", default=600, cast=int)

# Time in seconds of how long is required before a payment is deemed to be expired
PAYMENT_EXPIRY_TIME = config("PAYMENT_EXPIRY_TIME", default=120, cast=int)

ATLAS_URL = config("ATLAS_URL", default=None)

SCHEMES_COLLECTING_METRICS = config("SCHEMES_COLLECTING_METRICS", default="cooperative", cast=lambda x: x.split(","))

BinMatch = namedtuple("BinMatch", "type len value")
BIN_TO_PROVIDER = {
    "visa": [
        BinMatch(type="equal", len=1, value="4"),
    ],
    "amex": [BinMatch(type="equal", len=2, value="34"), BinMatch(type="equal", len=2, value="37")],
    "mastercard": [BinMatch(type="range", len=2, value=(51, 55)), BinMatch(type="range", len=4, value=(2221, 2720))],
}

INTERNAL_SERVICE_BUNDLE = config("INTERNAL_SERVICE_BUNDLE", default="com.bink.daedalus")
JWT_EXPIRY_TIME = config("JWT_EXPIRY_TIME", default=600, cast=int)


VAULT_CONFIG = {
    # Hashicorp vault settings for secrets retrieval
    "VAULT_URL": config("VAULT_URL", default=""),
    # SET Signing secrets for JWT authentication
    # For deployment set LOCAL_SECRETS to False and set up Vault envs
    # For local use without Vault, set LOCAL_SECRETS to True
    # and set LOCAL_SECRETS_PATH to your json file. See example_local_secrets.json for format
    # (Do not commit your local_secrets json which might contain real secrets or edit example_local_secrets.json)
    "LOCAL_SECRETS": config("LOCAL_SECRETS", default=False, cast=bool),
    "LOCAL_SECRETS_PATH": config("LOCAL_SECRETS_PATH", default="example_local_secrets.json"),
    "BUNDLE_SECRETS_NAME": config("BUNDLE_SECRETS_NAME", default="channels"),
    "SECRET_KEYS_NAME": config("SECRET_KEYS_NAME", default="secret-keys"),
    "AES_KEYS_NAME": config("AES_KEYS_NAME", default="aes-keys"),
}

CSRF_COOKIE_HTTPONLY = config("SECURE_COOKIES", default=False, cast=bool)
CSRF_COOKIE_SECURE = config("SECURE_COOKIES", default=False, cast=bool)
SESSION_COOKIE_HTTPONLY = config("SECURE_COOKIES", default=False, cast=bool)
SESSION_COOKIE_SECURE = config("SECURE_COOKIES", default=False, cast=bool)

# OIDC SSO
SSO_OFF = config("SSO_OFF", default=False, cast=bool)
LOGIN_REDIRECT_URL = "/admin/"
LOGIN_REDIRECT_URL_FAILURE = "/admin/error/403"
OIDC_RP_REPLY_URL = config("OIDC_RP_REPLY_URL", default="https://api.dev.gb.bink.com/admin/oidc/callback/")
OIDC_AUTHENTICATE_CLASS = "sso.auth.CustomOIDCAuthenticationRequestView"
OIDC_RP_CLIENT_ID = config("OIDC_CLIENT_ID", default="1a5d83f3-da1f-401c-ac5f-d41c3fa0d9ef")
OIDC_RP_CLIENT_SECRET = config("OIDC_CLIENT_SECRET", default="-NGSjpWWx_1w-6~.NkIl3lf~DC3Rg-.CMz")
OIDC_RP_SIGN_ALGO = "RS256"
OIDC_OP_JWKS_ENDPOINT = "https://login.microsoftonline.com/a6e2367a-92ea-4e5a-b565-723830bcc095/discovery/v2.0/keys"
OIDC_OP_AUTHORIZATION_ENDPOINT = (
    "https://login.microsoftonline.com/a6e2367a-92ea-4e5a-b565-723830bcc095/oauth2/v2.0/authorize"
)
OIDC_OP_TOKEN_ENDPOINT = "https://login.microsoftonline.com/a6e2367a-92ea-4e5a-b565-723830bcc095/oauth2/v2.0/token"
OIDC_OP_USER_ENDPOINT = "https://graph.microsoft.com/oidc/userinfo"
OIDC_RENEW_ID_TOKEN_EXPIRY_SECONDS = 60 * 30

PROMETHEUS_EXPORT_MIGRATIONS = False
PROMETHEUS_LATENCY_BUCKETS = (
    0.050,
    0.125,
    0.150,
    0.2,
    0.375,
    0.450,
    0.6,
    0.8,
    1.0,
    2.0,
    3.0,
    4.0,
    6.0,
    8.0,
    10.0,
    12.0,
    15.0,
    20.0,
    30.0,
    float("inf"),
)
PROMETHEUS_PUSH_GATEWAY = config("PROMETHEUS_PUSH_GATEWAY", default="http://localhost:9100")
PROMETHEUS_JOB = "hermes"

ENCRYPTED_VALUES_LENGTH_CONTROL = config("ENCRYPTED_VALUES_LENGTH_CONTROL", default=255, cast=int)

WAREHOUSE_QUEUE_NAME = config("WAREHOUSE_QUEUE_NAME", default="clickhouse_hermes")

# DJango 3/4 change
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

# WhiteNoise Static Files Serving
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

API_MESSAGING_RETRY_LIMIT = config("API_MESSAGING_RETRY_LIMIT", default=3, cast=int)

DATA_UPLOAD_MAX_NUMBER_FIELDS = 2000
HERMES_LOCAL = config("HERMES_LOCAL", default=False, cast=bool)
# allows manage.py test to discover pytest only tests
TEST_RUNNER = "hermes.pytest_runner.PytestTestRunner"
