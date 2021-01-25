import sys
from typing import Type

from django.contrib.postgres.fields import JSONField
from django.db import models

from history.enums import SchemeAccountJourney


class HistoricalBase(models.Model):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    CHANGE_TYPES = (
        (CREATE, CREATE),
        (UPDATE, UPDATE),
        (DELETE, DELETE),
    )

    created = models.DateTimeField(auto_now_add=True)
    change_type = models.CharField(max_length=6, choices=CHANGE_TYPES)
    instance_id = models.CharField(max_length=255)
    channel = models.CharField(max_length=255)
    change_details = models.CharField(max_length=255, blank=True)

    class Meta:
        abstract = True


class HistoricalCustomUser(HistoricalBase):
    body = JSONField()
    email = models.EmailField(verbose_name='email address', max_length=255, blank=True)
    external_id = models.CharField(max_length=255, blank=True)


class HistoricalPaymentCardAccount(HistoricalBase):
    user_id = models.IntegerField(null=True)
    body = JSONField()


class HistoricalSchemeAccount(HistoricalBase):
    user_id = models.IntegerField(null=True)
    body = JSONField()
    journey = models.CharField(
        max_length=8,
        choices=SchemeAccountJourney.as_tuple_tuple(),
        default=SchemeAccountJourney.NONE.value,
    )


class HistoricalPaymentCardAccountEntry(HistoricalBase):
    user_id = models.IntegerField(null=True)
    payment_card_account_id = models.IntegerField()


class HistoricalSchemeAccountEntry(HistoricalBase):
    user_id = models.IntegerField(null=True)
    scheme_account_id = models.IntegerField()


def _get_model(name: str) -> Type["models.Model"]:
    return getattr(sys.modules[__name__], name)


def get_historical_model(name: str) -> Type["models.Model"]:
    return _get_model(f"Historical{name}")
