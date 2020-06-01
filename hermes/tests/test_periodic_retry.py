from django.test import TestCase

from hermes.tasks import PeriodicRetryHandler
from payment_card.models import PeriodicRetryStatus, PeriodicRetry

test_generic_func_call_count = 0
test_retry_func_call_count = 0


def test_generic_func(arg):
    global test_generic_func_call_count
    test_generic_func_call_count += 1


def test_retry_func(data):
    global test_retry_func_call_count
    retry_obj = data["periodic_retry_obj"]

    if test_retry_func_call_count > 0:
        retry_obj.status = PeriodicRetryStatus.SUCCESSFUL

    test_retry_func_call_count += 1
    retry_obj.results += ["Retry results"]

    retry_obj.save(update_fields=["status", "results"])


def mock_retry_task(task_list: str) -> None:
    periodic_retry_handler = PeriodicRetryHandler(task_list=task_list)

    requests_to_retry = PeriodicRetry.objects.filter(
        task_group=task_list,
        status=PeriodicRetryStatus.REQUIRED
    )

    for retry_info in requests_to_retry:
        periodic_retry_handler.retry(retry_info)

    periodic_retry_handler.call_all_tasks()


class TestPeriodicRetry(TestCase):

    def setUp(self) -> None:
        global test_generic_func_call_count
        global test_retry_func_call_count

        test_generic_func_call_count = 0
        test_retry_func_call_count = 0

        self.test_task_list = "test_retry_tasks"
        self.handler = PeriodicRetryHandler(task_list=self.test_task_list)

        # empty task list
        for _ in range(self.handler.length):
            self.handler.storage.rpop(self.test_task_list)

    def test_retry_generic_function(self):
        retry_obj = self.handler.new("hermes.tests.test_periodic_retry", "test_generic_func", "some arg")
        self.assertEqual(retry_obj.status, PeriodicRetryStatus.PENDING)

        mock_retry_task(self.test_task_list)
        self.assertEqual(test_generic_func_call_count, 1)

        retry_obj.refresh_from_db(fields=["status"])
        self.assertEqual(retry_obj.status, PeriodicRetryStatus.REQUIRED)

        mock_retry_task(self.test_task_list)
        retry_obj.refresh_from_db(fields=["retry_count"])
        self.assertEqual(test_generic_func_call_count, 2)
        self.assertEqual(retry_obj.retry_count, 2)

    def test_retry_specific_retry_function(self):
        retry_obj = self.handler.new("hermes.tests.test_periodic_retry", "test_retry_func")
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

    def test_retry_halts_after_max_retry_attempts_is_reached(self):
        max_retry_attempts = 3
        retry_obj = self.handler.new(
            "hermes.tests.test_periodic_retry",
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

    def test_retry_existing_periodic_retry_object(self):
        retry_obj = self.handler.new(
            "hermes.tests.test_periodic_retry",
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

    def test_cannot_set_task_already_in_queue(self):
        retry_obj = self.handler.new("hermes.tests.test_periodic_retry", "test_generic_func", "some arg")
        self.assertEqual(len(self.handler.get_tasks_in_queue()), 1)

        self.handler.retry(retry_obj)
        self.assertEqual(len(self.handler.get_tasks_in_queue()), 1)
