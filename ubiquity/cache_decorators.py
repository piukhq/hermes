from json import loads, dumps

from django.conf import settings
from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from rest_framework.response import Response

from ubiquity.versioning import get_api_version

r = Redis(connection_pool=settings.REDIS_API_CACHE_POOL)


class CacheMissedError(Exception):
    pass


class ApiCache:

    def __init__(self, key, expire):
        self.key = key
        self.data = None
        self.expire = expire

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
            r.set(self.key, dumps(data), ex=self.expire)
        except RedisConnectionError:
            pass


def membership_plan_key(req):
    """
    This function generates a key part based on bundle_id string and user type
    ideal for membership plan decorators
    :param req: request object
    :return: key_part
    """
    user = getattr(req, 'user')
    user_tester = '1' if user and user.is_tester else '0'
    return f'{req.channels_permit.bundle_id}:{user_tester}'


class CacheApiRequest(object):

    def __init__(self, key_slug, expiry, key_func):
        """
        This decorator can be used to cache a get a versioned request which always returns 200 on success -
        request must be first parameter in function decorated. The key used will have key_slug and api version
        plus any additional string made by the key_func.
        :param key_slug: name part of cache key unique for requested to be cached
        :param expiry: expiry time of key
        :param key_function to generate additional key parameters from request
        """
        self.key_slug = key_slug
        self.expiry = expiry
        self.key_func = key_func

    def __call__(self, func):

        def wrapped_f(request, *args, **kwargs):
            req = request.request
            version = get_api_version(req)
            key = f"{self.key_slug}:{version}:{self.key_func(req)}"
            cache = ApiCache(key, self.expiry)
            if cache.available:
                response = Response(cache.data)
                response['X-API-Version'] = version
            else:
                response = func(request, *args, **kwargs)
                if response.status_code == 200:
                    cache.save(response.data)

            return response

        return wrapped_f
