from enum import IntEnum

from django.db import models
from django.db.models import JSONField

from payment_card.models import PaymentCardAccount


class RetryStatus(IntEnum):
    STOPPED = 0  # Retry is required
    RETRYING = 1  # Retry has been queued but is pending
    SUCCESSFUL = 2  # Retry was successful


class PeriodicRetain(models.Model):
    payment_card_account = models.OneToOneField(
        PaymentCardAccount,
        on_delete=models.CASCADE,
        primary_key=True,
    )
    status = models.IntegerField(
        choices=[(status.value, status.name) for status in RetryStatus], default=RetryStatus.RETRYING
    )
    message_key = models.CharField(max_length=80, null=True, blank=True)
    succeeded = models.BooleanField(default=False)
    retry_count = models.IntegerField(default=0, null=True, blank=True)
    results = JSONField(default=list, null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
