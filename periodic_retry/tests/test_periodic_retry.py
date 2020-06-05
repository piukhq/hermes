import time
from unittest.mock import patch

import arrow
import fakeredis
from django.test import TestCase

from periodic_retry.tasks import PeriodicRetryHandler, retry_metis_request_tasks
from periodic_retry.models import PeriodicRetryStatus, PeriodicRetry, RetryTaskList

test_generic_func_call_count = 0
test_retry_func_call_count = 0

server = fakeredis.FakeServer()
mock_redis = fakeredis.FakeStrictRedis(server=server)


def test_generic_func(arg):
    global test_generic_func_call_count
    test_generic_func_call_count += 1


def test_retry_func(data):
    global test_retry_func_call_count
    test_retry_func_call_count += 1

    retry_obj = data["periodic_retry_obj"]
    handler = data["periodic_retry_handler"]

    disable_max_test = data["context"].get("disable_max_test")

    if (test_retry_func_call_count > 1 and not disable_max_test or
            disable_max_test and test_retry_func_call_count >= handler.default_max_retry_count + 2):
        retry_obj.status = PeriodicRetryStatus.SUCCESSFUL

    retry_obj.results += ["Retry results"]

    retry_obj.save(update_fields=["status", "results"])


def mock_retry_task(task_list: str) -> None:
    time_now = arrow.utcnow().datetime
    periodic_retry_handler = PeriodicRetryHandler(task_list=task_list)

    requests_to_retry = PeriodicRetry.objects.filter(
        task_group=task_list,
        status=PeriodicRetryStatus.REQUIRED,
        next_retry_after__lte=time_now
    )

    for retry_info in requests_to_retry:
        periodic_retry_handler.retry(retry_info)

    periodic_retry_handler.call_all_tasks()


class TestPeriodicRetry(TestCase):

    @patch("periodic_retry.tasks.get_redis_connection")
    def setUp(self, mock_redis_connection) -> None:
        global test_generic_func_call_count
        global test_retry_func_call_count

        test_generic_func_call_count = 0
        test_retry_func_call_count = 0

        mock_redis_connection.return_value = mock_redis
        self.test_task_list = "test_retry_tasks"

        self.handler = PeriodicRetryHandler(task_list=self.test_task_list)

        # empty task list
        for _ in range(self.handler.length):
            self.handler.storage.rpop(self.test_task_list)

    def tearDown(self) -> None:
        # empty task list
        for _ in range(self.handler.length):
            self.handler.storage.rpop(self.test_task_list)

    @patch("periodic_retry.tasks.get_redis_connection")
    def test_retry_generic_function(self, mock_redis_connection):
        mock_redis_connection.return_value = mock_redis

        retry_obj = self.handler.new("periodic_retry.tests.test_periodic_retry", "test_generic_func", "some arg")
        self.assertEqual(retry_obj.status, PeriodicRetryStatus.PENDING)

        mock_retry_task(self.test_task_list)
        self.assertEqual(test_generic_func_call_count, 1)

        retry_obj.refresh_from_db(fields=["status"])
        self.assertEqual(retry_obj.status, PeriodicRetryStatus.REQUIRED)

        mock_retry_task(self.test_task_list)
        retry_obj.refresh_from_db(fields=["retry_count"])
        self.assertEqual(test_generic_func_call_count, 2)
        self.assertEqual(retry_obj.retry_count, 2)

    @patch("periodic_retry.tasks.get_redis_connection")
    def test_retry_tailored_retry_function(self, mock_redis_connection):
        mock_redis_connection.return_value = mock_redis

        retry_obj = self.handler.new("periodic_retry.tests.test_periodic_retry", "test_retry_func")
        self.assertEqual(retry_obj.status, PeriodicRetryStatus.PENDING)

        mock_retry_task(self.test_task_list)
        self.assertEqual(test_retry_func_call_count, 1)

        retry_obj.refresh_from_db(fields=["status"])
        self.assertEqual(retry_obj.status, PeriodicRetryStatus.REQUIRED)

        mock_retry_task(self.test_task_list)
        retry_obj.refresh_from_db(fields=["status", "retry_count"])
        self.assertEqual(retry_obj.status, PeriodicRetryStatus.SUCCESSFUL)
        self.assertEqual(test_retry_func_call_count, 2)
        self.assertEqual(retry_obj.retry_count, 2)

        mock_retry_task(self.test_task_list)
        retry_obj.refresh_from_db(fields=["retry_count", "results"])
        self.assertEqual(test_retry_func_call_count, 2)
        self.assertEqual(retry_obj.retry_count, 2)
        self.assertEqual(len(retry_obj.results), 2)

    @patch("periodic_retry.tasks.get_redis_connection")
    def test_retry_halts_after_max_retry_attempts_is_reached(self, mock_redis_connection):
        mock_redis_connection.return_value = mock_redis

        max_retry_attempts = 3
        retry_obj = self.handler.new(
            "periodic_retry.tests.test_periodic_retry",
            "test_generic_func",
            "some arg",
            retry_kwargs={"max_retry_attempts": max_retry_attempts}
        )

        for _ in range(5):
            mock_retry_task(self.test_task_list)

        retry_obj.refresh_from_db(fields=["retry_count"])
        self.assertEqual(test_generic_func_call_count, max_retry_attempts)
        self.assertEqual(retry_obj.retry_count, max_retry_attempts)
        self.assertEqual(test_generic_func_call_count, max_retry_attempts)

    @patch("periodic_retry.tasks.get_redis_connection")
    def test_retry_existing_periodic_retry_object(self, mock_redis_connection):
        mock_redis_connection.return_value = mock_redis

        retry_obj = self.handler.new(
            "periodic_retry.tests.test_periodic_retry",
            "test_generic_func",
            "some arg",
            retry_kwargs={"max_retry_attempts": 2}
        )
        self.assertEqual(len(self.handler.get_tasks_in_queue()), 1)

        mock_retry_task(self.test_task_list)
        self.assertEqual(len(self.handler.get_tasks_in_queue()), 0)

        retry_obj.refresh_from_db()
        self.handler.retry(retry_obj)
        self.assertEqual(len(self.handler.get_tasks_in_queue()), 1)

        mock_retry_task(self.test_task_list)

        retry_obj.refresh_from_db()
        self.assertEqual(len(self.handler.get_tasks_in_queue()), 0)
        self.assertEqual(retry_obj.retry_count, 2)

    @patch("periodic_retry.tasks.get_redis_connection")
    def test_cannot_set_task_already_in_queue(self, mock_redis_connection):
        mock_redis_connection.return_value = mock_redis

        retry_obj = self.handler.new("periodic_retry.tests.test_periodic_retry", "test_generic_func", "some arg")
        self.assertEqual(len(self.handler.get_tasks_in_queue()), 1)

        self.handler.retry(retry_obj)
        self.assertEqual(len(self.handler.get_tasks_in_queue()), 1)

    @patch("periodic_retry.tasks.get_redis_connection")
    def test_max_retry_can_be_disabled(self, mock_redis_connection):
        mock_redis_connection.return_value = mock_redis

        retry_count_success = self.handler.default_max_retry_count + 2
        retry_obj = self.handler.new(
            "periodic_retry.tests.test_periodic_retry",
            "test_retry_func",
            context={"disable_max_test": True},
            retry_kwargs={"max_retry_attempts": None}
        )

        # need to retry greater than 10 times since 10 is the default max
        for _ in range(retry_count_success):
            mock_retry_task(self.test_task_list)

        self.assertEqual(test_retry_func_call_count, retry_count_success)
        retry_obj.refresh_from_db(fields=["retry_count", "status"])
        self.assertEqual(retry_obj.retry_count, retry_count_success)
        self.assertEqual(retry_obj.status, PeriodicRetryStatus.SUCCESSFUL)

    @patch("periodic_retry.tasks.get_redis_connection")
    def test_retry_task_not_called_before_next_retry_after_value(self, mock_redis_connection):
        mock_redis_connection.return_value = mock_redis
        retry_after_seconds = 3

        retry_obj = self.handler.new(
            "periodic_retry.tests.test_periodic_retry",
            "test_retry_func",
            retry_kwargs={
                "next_retry_after": arrow.utcnow().shift(seconds=retry_after_seconds).datetime
            }
        )
        self.assertEqual(retry_obj.status, PeriodicRetryStatus.PENDING)

        mock_retry_task(self.test_task_list)
        self.assertEqual(test_retry_func_call_count, 0)

        time.sleep(retry_after_seconds)

        mock_retry_task(self.test_task_list)
        self.assertEqual(test_retry_func_call_count, 1)

    @patch("periodic_retry.tasks.get_redis_connection")
    def test_metis_requests_retry_only_queues_after_the_next_retry_after_field_datetime(self, mock_redis_connection):
        mock_redis_connection.return_value = mock_redis
        retry_after_seconds = 3

        retry_obj = PeriodicRetry.objects.create(
            task_group=RetryTaskList.METIS_REQUESTS,
            module="periodic_retry.tests.test_periodic_retry",
            function="test_generic_func",
            next_retry_after=arrow.utcnow().shift(seconds=retry_after_seconds).datetime
        )
        self.assertEqual(retry_obj.status, PeriodicRetryStatus.REQUIRED)

        retry_metis_request_tasks()
        self.assertEqual(test_generic_func_call_count, 0)

        time.sleep(retry_after_seconds)

        retry_metis_request_tasks()
        self.assertEqual(test_generic_func_call_count, 1)
