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

    # TODO allow empty user_id and change_reason (possibly rename as change_details)
    change_reason = models.CharField(max_length=255)
    user_id = models.IntegerField()

    class Meta:
        abstract = True


class HistoricalPaymentCardAccount(HistoricalBase):
    body = JSONField()


class HistoricalSchemeAccount(HistoricalBase):
    body = JSONField()


class HistoricalPaymentCardAccountEntry(HistoricalBase):
    payment_card_account_id = models.IntegerField()


class HistoricalSchemeAccountEntry(HistoricalBase):
    scheme_account_id = models.IntegerField()
