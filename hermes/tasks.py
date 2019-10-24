import importlib
import json

from celery import shared_task
from django_redis import get_redis_connection


@shared_task
def retry_tasks():
    # needs to try all tasks in list on each scheduled retry beat
    task_store = RetryTaskStore()
    for i in range(0, task_store.length):
        task_store.call_next_task()


class RetryTaskStore:

    def __init__(self, task_list="retrytasks", retry_name="retries", retry_results="errors"):

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
