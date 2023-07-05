from typing import Any
from unittest.mock import MagicMock, patch

import redis.exceptions
from django.test import TestCase
from redis.client import Redis

from hermes.redis import _CacheInfo, redis_cache


class Test:
    """
    Test class used for testing caching of a function
    which takes a class as an argument
    """

    pass


class TestCache(TestCase):
    @staticmethod
    def _test_function(arg) -> Any:
        return arg

    @staticmethod
    def _test_function2(arg) -> Any:
        return arg

    def test_cache_decorator_pickle(self):
        # no list, dict, or set because they're un-hashable
        expected_result = ((1, "2", True), self._test_function, Test)
        wrapped_fn = redis_cache(self._test_function)
        cache_info_fn_call_0 = wrapped_fn.cache_info()

        for result in expected_result:
            result1 = wrapped_fn(result)
            cache_info_fn_call_1 = wrapped_fn.cache_info()

            result2 = wrapped_fn(result)
            cache_info_fn_call_2 = wrapped_fn.cache_info()

            wrapped_fn.cache_clear()

            result3 = wrapped_fn(result)
            cache_info_fn_call_3 = wrapped_fn.cache_info()

            self.assertEqual(result, result1)
            self.assertEqual(result1, result2)
            self.assertEqual(result1, result3)
            self.assertEqual(_CacheInfo(json_hits=0, pickle_hits=0, misses=0), cache_info_fn_call_0)
            self.assertEqual(_CacheInfo(json_hits=0, pickle_hits=0, misses=1), cache_info_fn_call_1)
            self.assertEqual(_CacheInfo(json_hits=0, pickle_hits=1, misses=1), cache_info_fn_call_2)
            self.assertEqual(_CacheInfo(json_hits=0, pickle_hits=0, misses=1), cache_info_fn_call_3)
            wrapped_fn.cache_clear()

    def test_cache_decorator_json(self):
        expected_result = (1, "2", 1.1, True)
        wrapped_fn = redis_cache(self._test_function)
        cache_info_fn_call_0 = wrapped_fn.cache_info()

        for result in expected_result:
            result1 = wrapped_fn(result)
            cache_info_fn_call_1 = wrapped_fn.cache_info()

            result2 = wrapped_fn(result)
            cache_info_fn_call_2 = wrapped_fn.cache_info()

            wrapped_fn.cache_clear()

            result3 = wrapped_fn(result)
            cache_info_fn_call_3 = wrapped_fn.cache_info()

            self.assertEqual(result, result1)
            self.assertEqual(result1, result2)
            self.assertEqual(result1, result3)
            self.assertEqual(_CacheInfo(json_hits=0, pickle_hits=0, misses=0), cache_info_fn_call_0)
            self.assertEqual(_CacheInfo(json_hits=0, pickle_hits=0, misses=1), cache_info_fn_call_1)
            self.assertEqual(_CacheInfo(json_hits=1, pickle_hits=0, misses=1), cache_info_fn_call_2)
            self.assertEqual(_CacheInfo(json_hits=0, pickle_hits=0, misses=1), cache_info_fn_call_3)
            wrapped_fn.cache_clear()

    def test_cache_decorator_kwargs(self):
        expected_result = (1, "2", 1.1, True)
        wrapped_fn = redis_cache(self._test_function)
        cache_info_fn_call_0 = wrapped_fn.cache_info()

        for result in expected_result:
            result1 = wrapped_fn(arg=result)
            cache_info_fn_call_1 = wrapped_fn.cache_info()

            result2 = wrapped_fn(arg=result)
            cache_info_fn_call_2 = wrapped_fn.cache_info()

            wrapped_fn.cache_clear()

            result3 = wrapped_fn(arg=result)
            cache_info_fn_call_3 = wrapped_fn.cache_info()

            self.assertEqual(result, result1)
            self.assertEqual(result1, result2)
            self.assertEqual(result1, result3)
            self.assertEqual(_CacheInfo(json_hits=0, pickle_hits=0, misses=0), cache_info_fn_call_0)
            self.assertEqual(_CacheInfo(json_hits=0, pickle_hits=0, misses=1), cache_info_fn_call_1)
            self.assertEqual(_CacheInfo(json_hits=1, pickle_hits=0, misses=1), cache_info_fn_call_2)
            self.assertEqual(_CacheInfo(json_hits=0, pickle_hits=0, misses=1), cache_info_fn_call_3)
            wrapped_fn.cache_clear()

    def test_cache_decorator_redis_error(self):
        mock_redis = MagicMock()

        result = "test"
        wrapped_fn = redis_cache(self._test_function)
        cache_info_fn_call_0 = wrapped_fn.cache_info()

        wrapped_fn(arg=result)
        cache_info_fn_call_1 = wrapped_fn.cache_info()

        wrapped_fn(arg=result)
        cache_info_fn_call_2 = wrapped_fn.cache_info()

        expected_misses = 1
        for error in (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError):
            mock_redis.side_effect = error

            with patch.object(Redis, "get", mock_redis):
                result_after_err = wrapped_fn(arg=result)
                cache_info_fn_call_err = wrapped_fn.cache_info()
                expected_misses += 1

            self.assertEqual(_CacheInfo(json_hits=1, pickle_hits=0, misses=expected_misses), cache_info_fn_call_err)

        self.assertEqual(result, result_after_err)
        self.assertEqual(_CacheInfo(json_hits=0, pickle_hits=0, misses=0), cache_info_fn_call_0)
        self.assertEqual(_CacheInfo(json_hits=0, pickle_hits=0, misses=1), cache_info_fn_call_1)
        self.assertEqual(_CacheInfo(json_hits=1, pickle_hits=0, misses=1), cache_info_fn_call_2)

    def test_cache_decorator_multi_fn(self):
        """Tests that the cache and cache info is separate for different functions"""
        wrapped_fn1 = redis_cache(self._test_function)
        wrapped_fn2 = redis_cache(self._test_function2)

        result = "test"

        wrapped_fn1(result)
        wrapped_fn2(result)

        fn1_cache_info_1 = wrapped_fn1.cache_info()
        fn2_cache_info_1 = wrapped_fn2.cache_info()

        self.assertEqual(_CacheInfo(json_hits=0, pickle_hits=0, misses=1), fn1_cache_info_1)
        self.assertEqual(_CacheInfo(json_hits=0, pickle_hits=0, misses=1), fn2_cache_info_1)

        wrapped_fn1(result)

        fn1_cache_info_2 = wrapped_fn1.cache_info()
        fn2_cache_info_2 = wrapped_fn2.cache_info()

        self.assertEqual(_CacheInfo(json_hits=1, pickle_hits=0, misses=1), fn1_cache_info_2)
        self.assertEqual(_CacheInfo(json_hits=0, pickle_hits=0, misses=1), fn2_cache_info_2)

        wrapped_fn2.cache_clear()

        fn1_cache_info_3 = wrapped_fn1.cache_info()
        fn2_cache_info_3 = wrapped_fn2.cache_info()

        self.assertEqual(_CacheInfo(json_hits=1, pickle_hits=0, misses=1), fn1_cache_info_3)
        self.assertEqual(_CacheInfo(json_hits=0, pickle_hits=0, misses=0), fn2_cache_info_3)
