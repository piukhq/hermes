import functools
import json
import logging
import pickle
from collections import namedtuple
from collections.abc import Callable
from threading import RLock
from typing import Any

from django.conf import settings
from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

logger = logging.getLogger(__name__)

r_write = Redis(connection_pool=settings.REDIS_WRITE_API_CACHE_POOL)
r_read = Redis(connection_pool=settings.REDIS_READ_API_CACHE_POOL)


################################################################################
# Lifted and unchanged from functools to make a cache key from positional + keyword arguments
# that are passed into a decorated function
################################################################################
class _HashedSeq(list):
    """This class guarantees that hash() will be called no more than once
    per element.  This is important because the lru_cache() will hash
    the key multiple times on a cache miss.

    """

    __slots__ = "hashvalue"  # noqa: PLC0205

    def __init__(self, tup, hash=hash):  # noqa: A002
        self[:] = tup
        self.hashvalue = hash(tup)

    def __hash__(self):
        return self.hashvalue


def _make_key(
    args,
    kwds,
    typed,
    kwd_mark=(object(),),  # noqa: B008
    fasttypes={int, str},  # noqa: B006
    tuple=tuple,  # noqa: A002
    type=type,  # noqa: A002
    len=len,  # noqa: A002
):
    """Make a cache key from optionally typed positional and keyword arguments

    The key is constructed in a way that is flat as possible rather than
    as a nested structure that would take more memory.

    If there is only a single argument and its data type is known to cache
    its hash value, then that argument is returned without a wrapper.  This
    saves space and improves lookup speed.

    """
    # All of code below relies on kwds preserving the order input by the user.
    # Formerly, we sorted() the kwds before looping.  The new way is *much*
    # faster; however, it means that f(x=1, y=2) will now be treated as a
    # distinct call from f(y=2, x=1) which will be cached separately.
    key = args
    if kwds:
        key += kwd_mark
        for item in kwds.items():
            key += item
    if typed:
        key += tuple(type(v) for v in args)
        if kwds:
            key += tuple(type(v) for v in kwds.values())
    elif len(key) == 1 and type(key[0]) in fasttypes:
        return key[0]
    return _HashedSeq(key)


################################################################################
################################################################################

_CacheInfo = namedtuple("CacheInfo", ["json_hits", "pickle_hits", "misses"])


def redis_cache(user_function: Any) -> Callable:
    """
    Decorator to cache the result of a function in redis. This works similar to lru_cache from functools,
    and can be used as a drop-in replacement, but using a redis backend instead of caching in-memory.
    This also does not implement the least recently used eviction strategy and will use whichever configuration
    is set for Redis for its eviction strategy.

    Using a Redis backend for the cache allows sharing a cache between processes, which can be cleared by
    any process with the cache_clear() method.

    :param user_function: function to be decorated
    """
    lock = RLock()
    user_fn_id = f"{user_function.__module__}.{user_function.__code__.co_qualname}"
    json_hits = pickle_hits = misses = 0

    @functools.wraps(user_function)
    def wrapper(*args, **kwargs) -> Any:
        nonlocal json_hits, pickle_hits, misses

        # add a prefix to allow easier clearing of the function cache without affecting
        # other items stored in redis
        key = f"fn_cache:{user_fn_id}:{hash(_make_key(args, kwargs, typed=False))}"

        try:
            raw_result = r_read.get(key)
            if raw_result is not None:
                result_data = json.loads(raw_result)
                if result_data["is_json_serializable"]:
                    result = result_data["value"]
                    json_hits += 1
                else:
                    # Use pickle to preserve datatype since redis client stores and retrieves bytes.
                    # Since the arguments need to be hashable, this cache decorator will only use pickling
                    # for data types that can be hashed, such as tuples, functions, classes etc.
                    # This likely has a performance impact, so we use json for simple data types.
                    result = pickle.loads(result_data["value"].encode("latin1"))
                    pickle_hits += 1
            else:
                result = user_function(*args, **kwargs)
                if isinstance(result, (str | int | bool | float)):
                    value = {"is_json_serializable": True, "value": result}
                else:
                    value = {"is_json_serializable": False, "value": pickle.dumps(result).decode("latin1")}

                r_write.set(key, json.dumps(value))
                misses += 1
        except (RedisTimeoutError, RedisConnectionError):
            logger.error("Could not connect to Redis when attempting to retrieve cached data")
            # Just return the function result and don't attempt to set cache since we might just
            # run into another connection error, which could be slower than re-calculating the result
            misses += 1
            result = user_function(*args, **kwargs)

        return result

    def cache_clear() -> None:
        """Clear the cache"""
        nonlocal json_hits, pickle_hits, misses
        with lock:
            pipe = r_write.pipeline()
            for keys in r_write.scan_iter(f"fn_cache:{user_fn_id}:*", settings.REDIS_API_CACHE_SCAN_BATCH_SIZE):
                pipe.delete(keys)

            pipe.execute()
            json_hits = pickle_hits = misses = 0

    def cache_info() -> tuple:
        """Retrieve info on cache hits and misses"""
        with lock:
            return _CacheInfo(json_hits, pickle_hits, misses)

    wrapper.cache_clear = cache_clear
    wrapper.cache_info = cache_info
    return wrapper
