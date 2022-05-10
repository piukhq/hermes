from django.conf import settings
from django.db import OperationalError, connection
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods
from kombu.exceptions import ConnectionError as KombuConnectionError
from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError

from api_messaging.message_broker import BaseMessaging


def test_database(error_response: dict):
    try:
        with connection.cursor() as cursor:
            cursor.execute("select 1")
            one = cursor.fetchone()[0]
            if one == 1:
                # Ok
                del error_response["database"]
    except OperationalError as e:
        error_response["database_exception"] = str(e)


def test_rabbit(error_response: dict):
    try:
        conn = BaseMessaging(settings.RABBIT_DSN).conn
        if conn.connect():
            del error_response["rabbit"]
        conn.close()
    except (ConnectionError, KombuConnectionError) as e:
        error_response["rabbit_exception"] = str(e)


def test_redis(error_response: dict):
    redis_write = False
    try:
        r_write = Redis(connection_pool=settings.REDIS_WRITE_API_CACHE_POOL)
        if r_write.ping():
            redis_write = True
        r_write.close()
    except (RedisConnectionError, ConnectionError) as e:
        error_response["redis_write_pool_exception"] = str(e)
    try:
        r_read = Redis(connection_pool=settings.REDIS_READ_API_CACHE_POOL)
        if r_read.ping() and redis_write:
            del error_response["redis"]
        r_read.close()
    except (RedisConnectionError, ConnectionError) as e:
        error_response["redis_read_pool_exception"] = str(e)


@require_http_methods(["GET"])
def live_z(request):
    return HttpResponse(status=204)


@require_http_methods(["GET"])
def ready_z(request):
    error_response = {
        "database": False,
        "rabbit": False,
        "redis": False,
    }
    test_database(error_response)
    test_rabbit(error_response)
    test_redis(error_response)
    if error_response:
        status = 500
    else:
        status = 200
    return JsonResponse(error_response, status=status)
