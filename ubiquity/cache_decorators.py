from json import loads, dumps

from django.conf import settings
from django.http import JsonResponse
from redis import ConnectionPool, Redis
from redis.exceptions import ConnectionError as RedisConnectionError

pool = ConnectionPool(host=settings.REDIS_HOST, port=settings.REDIS_PORT,
                      password=settings.REDIS_PASSWORD, db=settings.REDIS_API_CACHE_DB)
r = Redis(connection_pool=pool)


class CacheMissedError(Exception):
    pass


class ApiCache:

    def __init__(self, req):
        user = getattr(req, 'user')
        user_tester = '1' if user and user.is_tester else '0'
        self.key = f"m_plans:{req.version}:{req.channels_permit.bundle_id}:{user_tester}"
        self.data = None

    @property
    def available(self):
        try:
            response_json = r.get(self.key)
            if response_json:
                self.data = loads(response_json)
                return True
            else:
                raise CacheMissedError
        except (RedisConnectionError, CacheMissedError):
            self.data = None
            return False

    def save(self, data):
        try:
            r.set(self.key, dumps(data), ex=settings.REDIS_API_CACHE_EXPIRY)
        except RedisConnectionError:
            pass


def cache_membership_plans(func):
    def func_wrapper(request, *args, **kwargs):
        req = request.request
        cache = ApiCache(req)
        if cache.available:
            response = JsonResponse(cache.data, safe=False)
            response['X-API-Version'] = req.version
        else:
            response = func(request, *args, **kwargs)
            if response.status_code == 200:
                cache.save(response.data)

        return response

    return func_wrapper
