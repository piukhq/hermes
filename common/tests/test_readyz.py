import json
from unittest.mock import patch

from django.conf import settings
from django.db import OperationalError
from kombu import Connection
from kombu.exceptions import ConnectionError as KombuConnectionError
from redis.exceptions import ConnectionError as RedisConnectionError
from rest_framework.test import APITestCase

from common.views import Redis as RedisTarget
from common.views import connection


def mock_cursor():
    raise OperationalError("Mock Connection Error")


def mock_rabbit_con():
    raise KombuConnectionError("Mock Connection Error")


def mock_redis_init(**kwargs):
    if kwargs["connection_pool"] == settings.REDIS_WRITE_API_CACHE_POOL:
        raise RedisConnectionError("Redis Mock Write Connection Error")
    else:
        raise RedisConnectionError("Redis Mock Read Connection Error")


class TestReadyZ(APITestCase):
    def test_ok(self):
        resp = self.client.get("/readyz")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, b"{}")

    @patch.object(connection, "cursor")
    def test_db_fail(self, mock_db_connect):
        mock_db_connect.side_effect = mock_cursor
        resp = self.client.get("/readyz")
        self.assertEqual(resp.status_code, 500)
        dict_resp = json.loads(resp.content)
        self.assertFalse(dict_resp["database"])
        self.assertEqual(dict_resp["database_exception"], "Mock Connection Error")

    @patch.object(Connection, "connect")
    def test_rabbit_fail(self, mock_rabbit_connect):
        mock_rabbit_connect.side_effect = mock_rabbit_con
        resp = self.client.get("/readyz")
        self.assertEqual(resp.status_code, 500)
        dict_resp = json.loads(resp.content)
        self.assertFalse(dict_resp["rabbit"])
        self.assertEqual(dict_resp["rabbit_exception"], "Mock Connection Error")

    @patch.object(RedisTarget, "__init__")
    def test_redis_fail(self, mock_redis):
        mock_redis.side_effect = mock_redis_init
        resp = self.client.get("/readyz")
        self.assertEqual(resp.status_code, 500)
        dict_resp = json.loads(resp.content)
        self.assertFalse(dict_resp["redis"])
        self.assertEqual(dict_resp["redis_write_pool_exception"], "Redis Mock Write Connection Error")
        self.assertEqual(dict_resp["redis_read_pool_exception"], "Redis Mock Read Connection Error")
