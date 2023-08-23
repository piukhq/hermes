from unittest.mock import patch

import fakeredis
from django.conf import settings
from django.test.testcases import TestCase

from scheme.tasks import delete_membership_plans_cache

server = fakeredis.FakeServer()
mock_redis = fakeredis.FakeStrictRedis(server=server)


class TestCache(TestCase):
    @patch("scheme.tasks.redis_client", mock_redis)
    def test_delete_mplans_cache(self) -> None:
        for i in range(50):
            mock_redis.set(f"{settings.REDIS_MPLANS_CACHE_PREFIX}:{i}", "foo")
        delete_membership_plans_cache()

        for i in range(50):
            assert mock_redis.exists(f"m_plans:{i}") == 0
