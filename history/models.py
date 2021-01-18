from django.contrib.postgres.fields import JSONField
from django.db import models


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
    user_id = models.IntegerField(null=True)

    class Meta:
        abstract = True


class HistoricalPaymentCardAccount(HistoricalBase):
    body = JSONField()


class HistoricalSchemeAccount(HistoricalBase):
    ADD = "add"
    ENROL = "enrol"
    REGISTER = "register"
    JOURNEY_TYPES = (
        (ADD, ADD),
        (ENROL, ENROL),
        (REGISTER, REGISTER),
    )
    journey = models.CharField(max_length=8, choices=JOURNEY_TYPES)
    body = JSONField()


class HistoricalPaymentCardAccountEntry(HistoricalBase):
    payment_card_account_id = models.IntegerField()


class HistoricalSchemeAccountEntry(HistoricalBase):
    scheme_account_id = models.IntegerField()
