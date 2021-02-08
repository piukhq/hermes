import logging
import uuid
from json import loads, dumps

from django.conf import settings
from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError
from rest_framework.response import Response

from ubiquity.versioning import get_api_version
from time import monotonic

logger = logging.getLogger(__name__)
r_write = Redis(connection_pool=settings.REDIS_WRITE_API_CACHE_POOL)
r_read = Redis(connection_pool=settings.REDIS_READ_API_CACHE_POOL)


class CacheMissedError(Exception):
    pass


class ApiCache:

    def __init__(self, key, expire):
        self.key = key
        self.data = None
        self.expire = expire

    @staticmethod
    def time_it_log(start_time, subject, high=450, low=150):
        taken = int((monotonic() - start_time) * 1000)
        if taken > high:
            logger.warning(f"ApiCache: {subject} took too long at {taken} ms")
        elif taken > low:
            logger.warning(f"ApiCache: {subject} took longer than expected at {taken} ms")

    def get(self):
        # Pass below uuid into logs to map multiple retry errors of the same request over multiple log lines.
        # We log every timeout to get an understanding of how many times Azure Redis is slow to respond
        log_id = uuid.uuid4()
        retry_exception = CacheMissedError
        total_retries = settings.REDIS_RETRY_COUNT
        for retry_count in range(total_retries):
            try:
                response_json = r_read.get(self.key)
                return response_json
            except (RedisTimeoutError, RedisConnectionError) as e:
                retry_exception = e
                remaining_retries = total_retries - retry_count - 1
                # uuid passed into the logs to map multiple logs together with one request
                logger.warning(f"Get plan cache from Redis failed. Retrying {remaining_retries} more times. "
                               f"Error: {repr(e)}, Log ID: {log_id}")
        else:
            raise retry_exception

    @property
    def available(self):
        start_time = monotonic()
        try:
            response_json = self.get()
            if response_json:
                self.data = loads(response_json)
                self.time_it_log(start_time, "Success; Got plan cache from Redis but")
                return True
            else:
                raise CacheMissedError
        except (RedisConnectionError, RedisTimeoutError, CacheMissedError):
            self.data = None
            self.time_it_log(start_time, "Failure; Did not Get plan cache from Redis and")
            return False

    def save(self, data):
        save_time = monotonic()
        try:
            r_write.set(self.key, dumps(data), ex=self.expire)
            self.time_it_log(save_time, "Success; wrote plan cache to Redis but")
        except RedisConnectionError:
            self.time_it_log(save_time, "Failure; did not write plan cache to Redis and", low=0)
            pass


def membership_plan_key(req, kwargs=None):
    """
    This function generates a key part based on bundle_id string and user type
    ideal for membership plan decorators
    :param req: request object
    :param kwargs: additional parameters defined in the cache decorator for this function
    :return: key_part
    """
    user = getattr(req, 'user')
    user_tester = '1' if user and user.is_tester else '0'
    pk = kwargs.get('pk', "")
    pk_part = ""
    if pk:
        pk_part = f':{pk}'
    return f'{pk_part}:{req.channels_permit.bundle_id}:{user_tester}'


class CacheApiRequest(object):

    def __init__(self, key_slug, expiry, key_func):
        """
        This decorator can be used to cache a get a versioned request which always returns 200 on success -
        request must be first parameter in function decorated. The key used will have key_slug and api version
        plus any additional string made by the key_func.
        :param key_slug: name part of cache key unique for requested to be cached
        :param expiry: expiry time of key
        :param key_func: Function name to generate additional key parameters from request and/or cache decorator
        """
        self.key_slug = key_slug
        self.expiry = expiry
        self.key_func = key_func

    def __call__(self, func):

        def wrapped_f(request, *args, **kwargs):
            request_start_time = monotonic()
            cache_hit = "HIT"
            req = request.request
            version = get_api_version(req)
            key = f"{self.key_slug}{self.key_func(req, kwargs)}:{version}"
            cache = ApiCache(key, self.expiry)
            if cache.available:
                response = Response(cache.data)
                response['X-API-Version'] = version
            else:
                cache_hit = "MISS"
                response = func(request, *args, **kwargs)
                if response.status_code == 200:
                    cache.save(response.data)
                else:
                    logger.error(f"ApiCache: could not regenerate cache due to request error {response.status_code}")

            cache.time_it_log(request_start_time,
                              f"Request Response for {self.key_slug} key:{key} with Cache {cache_hit} ",
                              high=450,
                              low=350)
            return response

        return wrapped_f
