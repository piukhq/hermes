from django.contrib.postgres.fields import JSONField
from django.db import models


class SchemeAccountEntry(models.Model):
    scheme_account = models.ForeignKey('scheme.SchemeAccount')
    user = models.ForeignKey('user.CustomUser')
    membership_card_data = JSONField(default=dict())

    class Meta:
        unique_together = ("scheme_account", "user")


class PaymentCardAccountEntry(models.Model):
    payment_card_account = models.ForeignKey('payment_card.PaymentCardAccount')
    user = models.ForeignKey('user.CustomUser')
    payment_card_data = JSONField(default=dict())

    class Meta:
        unique_together = ("payment_card_account", "user")
