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
    """
    A handler class to set tasks that should be retried periodically. New tasks can be assigned
    for retry using the .new() method. This will create a PeriodicRetry object in
    PeriodicRetryStatus.REQUIRED status and should be initialised with all the necessary information
    to retry a function call.

    PeriodicRetry objects will be retried until one of two conditions are met:
     - The number of retries performed has reached the value of the .max_retry_attempts property
     - The status is set to something other than PENDING or REQUIRED in the retried function

    A periodic Celery task should be used to check if any PeriodicRetry objects are in the REQUIRED
    status, add them to the queue, and retry all tasks in the queue. This task should re-add the
    PeriodicRetry objects to the queue by using the .retry() method.

    Usage:

        General functions:
            This class allows for retrying of any normal function e.g

            def some_func(arg1, arg2, kwarg1="some_kwarg"):
                ...
                return


            The function above can be retried with the following:

            PeriodicRetryHandler(task_list=RetryTaskList.DEFAULT).new(
                'hermes.tasks', 'some_func', 'arg1', 'arg2', kwarg1="different_kwarg",
                retry_kwargs={"max_retry_attempts": 3}
            )

            Additional property values for PeriodicRetry, such as the max_retry_attempts,
            can be passed in as a dict to retry_kwargs. If nothing is passed in, the max_retry_attempts
            defaults to 10


        Tailored Retry Functions:
            Using a function that is specifically for retrying can allow more control and information
            logging. For example, a task can be retried indefinitely until it is successful by
            setting PeriodicRetry.status to SUCCESS only when it succeeds. This also requires disabling
            max_retry_attempts which can be done by passing it to the .new() function with a value of None.

            This also allows recording of each task outcome as a list in the PeriodicRetry.result attribute,
            which could be used for just logging purposes or even finer control.

            These functions should only accept one argument, which will be a dictionary containing
            the PeriodicRetry instance. Any additional data can be passed to the function as a dictionary
            via the context argument in .new()

            def retry_func(data):
                retry_obj = data["periodic_retry_obj"]

                    if (some_success_case):
                        retry_obj.status = PeriodicRetryStatus.SUCCESSFUL

                    retry_obj.results += ["Retry results"]
                    retry_obj.save()

            PeriodicRetryHandler(task_list=RetryTaskList.DEFAULT).new(
                'hermes.tasks',
                'some_func',
                context={"additional_data": True}
                retry_kwargs={"max_retry_attempts": None}
            )

    """

    def __init__(self, task_list: RetryTaskList):
        self.task_list = task_list
        self.warning_attempt_count = 5
        self.default_max_retry_count = 10
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

        logger.info(f"PeriodicRetry (id={retry_info.id}) added to {self.task_list} queue")

    def new(self, module_name: str, function_name: str, *args, retry_kwargs: dict = None,
            context: dict = None, **kwargs) -> PeriodicRetry:
        """Creates a new PeriodicRetry object and adds to the retry queue"""
        data = {
            "args": args,
            "kwargs": kwargs,
            "context": context or {},
        }

        if retry_kwargs is None:
            # Default max number of retries to 10 to avoid infinite retries
            # This can be bypassed by providing None for this value
            retry_kwargs = {"max_retry_attempts": self.default_max_retry_count}

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
        try:
            periodic_retry_obj = PeriodicRetry.objects.get(pk=data["task_id"])
        except KeyError:
            logger.exception(
                f"PeriodicRetry improperly set. Missing 'task_id' in data when calling task."
            )
            return

        logger.debug(f"Attempting to retry PeriodicRetry (id={periodic_retry_obj.id})")
        try:
            data["periodic_retry_obj"] = periodic_retry_obj
            data["periodic_retry_handler"] = self
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

        except Exception as e:
            # All exceptions caught and logged in results since it is impossible to know explicitly which exceptions
            # could be raised by a retried function. This also means execution of tasks will not be blocked if an
            # exception is raised by an earlier one.
            periodic_retry_obj.results += [str(e)]
            logger.exception(f"Error retrying PeriodicRetry (id={periodic_retry_obj.id})")

    def call_all_tasks(self):
        logger.info(f"Executing tasks on {self.task_list} queue")
        for i in range(0, self.length):
            self.call_next_task()

    def get_tasks_in_queue(self) -> list:
        tasks_in_queue = self.storage.lrange(
            name=self.task_list,
            start=0,
            end=self.length
        )
        return [json.loads(task) for task in tasks_in_queue]
