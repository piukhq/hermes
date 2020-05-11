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


class PeriodicRetryHandler:

    def __init__(self, task_list: RetryTaskList = None, task_store: RetryTaskStore = None):
        self.warning_msg_after_attempt_count = 5
        self.retry_func_wrapper_name = "retry_func_wrapper"

        if not task_store and not task_list:
            raise TypeError(f"{self.__name__} requires either a task_list or task_store argument")

        if task_store:
            self.task_store = task_store
        else:
            self.task_store = RetryTaskStore(task_list=task_list)

    def new(self, module_name, function_name, *args, **kwargs):
        data = {"args": args, "kwargs": kwargs}
        retry_task = PeriodicRetry.objects.create(
            module=module_name,
            function=function_name,
            data=data
        )

        self._set_task(retry_task, module_name, function_name, data)

    def _set_task(self, retry_info, module_name, function_name, data):
        data["periodic_retry_id"] = retry_info.id

        self._prechecks(retry_info)
        self.task_store.set_task(
            module_name=module_name,
            function_name=function_name,
            data=data
        )
        retry_info.status = PeriodicRetryStatus.PENDING
        retry_info.save()

    def call_next_task(self):

        # TODO: statuses should be set in the specific retry function when implemented
        # TODO: do not allow retry if max_retry_attempts is not none and retry_count => max_retry_attempts
        # TODO: check if a task is already queued when setting a task in _prechecks
        # TODO: logging + testing


        data = None
        try:
            data = json.loads(self.task_store.storage.rpop(self.task_store.task_list))

            periodic_retry_obj = PeriodicRetry.objects.get(data["periodic_retry_id"])

            if data:
                module = importlib.import_module(data["_module"])
                func = getattr(module, data["_function"])
                args, kwargs = (data.get("args", {}), data.get("kwargs", {}))
                if args or kwargs:
                    done, message = func(*data.get("args", {}), **data.get("kwargs", {}))
                else:
                    done, message = func(data)
                if not done:
                    if self.task_store.retry_results in data:
                        data[self.task_store.retry_results].append(message)
                    if data[self.task_store.retry_name] > 0:
                        self.task_store.save_to_redis(data)

                periodic_retry_obj.retry_count += 1
                periodic_retry_obj.next_retry_after = arrow.utcnow().shift(seconds=settings.RETRY_PERIOD)
                periodic_retry_obj.save()

        except IOError as e:
            if self.task_store.retry_results in data:
                data[self.task_store.retry_results].append(str(e))
            self.task_store.save_to_redis(data)

    def call_all_tasks(self):
        for i in range(0, self.task_store.length):
            self.task_store.call_next_task()

    def get_tasks_in_queue(self) -> list:
        tasks_in_queue = self.task_store.storage.lrange(
            name=self.task_store.task_list,
            start=0,
            end=self.task_store.length
        )

        return [json.loads(task) for task in tasks_in_queue]

    def _prechecks(self, periodic_retry_obj):
        if periodic_retry_obj.retry_count > self.warning_msg_after_attempt_count:
            sentry_sdk.capture_message(
                f"A periodic retry has failed 10 retry attempts. "
                f"(PeriodicRetry id={periodic_retry_obj.id})",
                level=logging.WARNING
            )
