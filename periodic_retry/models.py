from enum import IntEnum, Enum

from django.contrib.postgres.fields import JSONField
from django.db import models
from django.utils import timezone


class RetryTaskList(str, Enum):
    DEFAULT = "retrytasks"
    METIS_REQUESTS = "metis_request_retry_tasks"


class PeriodicRetryStatus(IntEnum):
    REQUIRED = 0      # Retry is required
    PENDING = 1       # Retry has been queued but is pending
    SUCCESSFUL = 2    # Retry was successful
    FAILED = 3        # Retry attempt failed


class PeriodicRetry(models.Model):
    # for identifying a group of tasks
    task_group = models.CharField(
        max_length=255,
        choices=[(task_list.value, task_list.name) for task_list in RetryTaskList]
    )
    status = models.IntegerField(
        choices=[(status.value, status.name) for status in PeriodicRetryStatus],
        default=PeriodicRetryStatus.REQUIRED
    )
    module = models.CharField(max_length=64)
    function = models.CharField(max_length=64)
    data = JSONField(default=dict, null=True, blank=True)
    retry_count = models.IntegerField(default=0, null=True, blank=True)
    max_retry_attempts = models.IntegerField(null=True, blank=True)
    results = JSONField(default=list, null=True, blank=True)

    # Retry is done via polling which will not allow retrying at an exact time.
    # next_retry_after indicates a minimum time before the next retry attempt.
    next_retry_after = models.DateTimeField(default=timezone.now, null=True, blank=True)
    created_on = models.DateTimeField(auto_now_add=True)
    modified_on = models.DateTimeField(auto_now=True)
