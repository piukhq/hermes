import importlib
import json
import logging
from enum import Enum

import arrow
import sentry_sdk
from celery import shared_task
from django_redis import get_redis_connection
from django.conf import settings

from payment_card.models import PeriodicRetry, PeriodicRetryStatus


logger = logging.getLogger(__name__)


class RetryTaskList(str, Enum):
    DEFAULT = "retrytasks"
    METIS_REQUESTS = "metis_request_retry_tasks"


@shared_task
def retry_tasks():
    # needs to try all tasks in list on each scheduled retry beat
    task_store = RetryTaskStore()
    for i in range(0, task_store.length):
        task_store.call_next_task()


class RetryTaskStore:

    def __init__(self, task_list=RetryTaskList.DEFAULT, retry_name="retries", retry_results="errors"):

        self.task_list = task_list
        self.retry_name = retry_name
        self.retry_results = retry_results
        self.storage = get_redis_connection('retry_tasks')

    @property
    def length(self):
        return self.storage.llen(self.task_list)

    def save_to_redis(self, data):
        if data[self.retry_name] > 0:
            self.storage.lpush(self.task_list, json.dumps(data))

    def set_task(self, module_name, function_name,  data):
        """
        Sets a task to retry from a module and function name. The task function must return
        a tuple: (done: Boolean, message: String)
        :param module_name:
        :param function_name:
        :param data:
        :return:
        """
        if not data.get(self.retry_name, False):
            data[self.retry_name] = 10              # default to 10 retries
        data["_module"] = module_name
        data["_function"] = function_name
        self.save_to_redis(data)

    def call_next_task(self):
        """Takes a retry task from top of list, calls the requested module and function passing the saved data and
        continues until retries has counted down to zero or when True is returned (this means done not necessarily
        successful ie fatal errors may return true to prevent retries)

        :return:
        """
        data = None
        try:
            data = json.loads(self.storage.rpop(self.task_list))
            if data:
                data[self.retry_name] -= 1
                module = importlib.import_module(data["_module"])
                func = getattr(module, data["_function"])
                done, message = func(data)
                if not done:
                    if self.retry_results in data:
                        data[self.retry_results].append(message)
                    if data[self.retry_name] > 0:
                        self.save_to_redis(data)

        except IOError as e:
            if self.retry_results in data:
                data[self.retry_results].append(str(e))
            self.save_to_redis(data)


class RetryError(Exception):
    pass


class PeriodicRetryHandler:

    def __init__(self, task_list: RetryTaskList):
        self.task_list = task_list
        self.warning_attempt_count = 5
        self.storage = get_redis_connection('retry_tasks')

    @property
    def length(self):
        return self.storage.llen(self.task_list)

    def save_to_redis(self, data):
        self.storage.lpush(self.task_list, json.dumps(data))

    def _set_task_prechecks(self, periodic_retry_obj: PeriodicRetry) -> None:
        tasks_in_queue = self.get_tasks_in_queue()
        ids_in_queue = [task["task_id"] for task in tasks_in_queue]

        if periodic_retry_obj.id in ids_in_queue:
            msg = f"PeriodicRetry object (id={periodic_retry_obj.id}) is already queued for retry"
            logger.debug(msg)
            raise RetryError(msg)

        if (periodic_retry_obj.max_retry_attempts and
                periodic_retry_obj.retry_count >= periodic_retry_obj.max_retry_attempts):
            msg = f"PeriodicRetry (id={periodic_retry_obj.id}) has reached the maximum retry attempts"
            periodic_retry_obj.results = periodic_retry_obj.results + [msg]
            periodic_retry_obj.status = PeriodicRetryStatus.FAILED
            periodic_retry_obj.save()
            logger.debug(msg)
            raise RetryError(msg)

        if (periodic_retry_obj.retry_count > 0 and
                periodic_retry_obj.retry_count % self.warning_attempt_count == 0):
            msg = f"PeriodicRetry (id={periodic_retry_obj.id}) has failed " \
                  f"{periodic_retry_obj.retry_count} retry attempts."
            sentry_sdk.capture_message(msg, level=logging.WARNING)
            logger.debug(msg)

    def _call_task_prechecks(self, periodic_retry_obj: PeriodicRetry) -> None:
        pass

    def _set_task(self, retry_info: PeriodicRetry, module_name: str, function_name: str, data: dict) -> None:
        data["task_id"] = retry_info.id
        data["_module"] = module_name
        data["_function"] = function_name
        try:
            self._set_task_prechecks(retry_info)
        except RetryError:
            logger.debug(f"Skipping adding task to retry queue... PeriodicRetry (id={retry_info.id})")
            return

        self.save_to_redis(data)
        retry_info.status = PeriodicRetryStatus.PENDING
        retry_info.save()

        logger.debug(f"PeriodicRetry (id={retry_info.id}) added to {self.task_list} queue")

    def new(self, module_name: str, function_name: str, *args, retry_kwargs: dict = None, **kwargs) -> PeriodicRetry:
        """Creates a new PeriodicRetry object and adds to the retry queue"""
        data = {"args": args, "kwargs": kwargs}

        if retry_kwargs is None:
            # Default max number of retries to 10 to avoid infinite retries
            # This can be bypassed by providing None for this value
            retry_kwargs = {"max_retry_attempts": 10}

        retry_task = PeriodicRetry.objects.create(
            task_group=self.task_list,
            module=module_name,
            function=function_name,
            data=data,
            **retry_kwargs
        )

        self._set_task(retry_task, module_name, function_name, data)
        return retry_task

    def retry(self, retry_obj: PeriodicRetry) -> None:
        """Adds an existing PeriodicRetry object to the retry queue"""
        self._set_task(retry_obj, retry_obj.module, retry_obj.function, retry_obj.data)

    def call_next_task(self):
        data = json.loads(self.storage.rpop(self.task_list))
        periodic_retry_obj = PeriodicRetry.objects.get(pk=data["task_id"])
        data["periodic_retry_obj"] = periodic_retry_obj
        try:
            self._call_task_prechecks(periodic_retry_obj)
            if data:
                module = importlib.import_module(data["_module"])
                func = getattr(module, data["_function"])
                args, kwargs = (data.get("args", {}), data.get("kwargs", {}))
                if args or kwargs:
                    func(*args, **kwargs)
                else:
                    func(data)

                if periodic_retry_obj.status == PeriodicRetryStatus.PENDING:
                    # Assumes retry is still required since the status was not changed in retried function
                    periodic_retry_obj.status = PeriodicRetryStatus.REQUIRED

                periodic_retry_obj.retry_count += 1
                periodic_retry_obj.next_retry_after = arrow.utcnow().shift(seconds=int(settings.RETRY_PERIOD)).datetime
                periodic_retry_obj.save()

        except IOError as e:
            periodic_retry_obj.results += str(e)

    def call_all_tasks(self):
        for i in range(0, self.length):
            self.call_next_task()

    def get_tasks_in_queue(self) -> list:
        tasks_in_queue = self.storage.lrange(
            name=self.task_list,
            start=0,
            end=self.length
        )
        return [json.loads(task) for task in tasks_in_queue]
