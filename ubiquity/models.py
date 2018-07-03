from django.db import models


class PaymentCardSchemeEntry(models.Model):
    payment_card_account = models.ForeignKey('payment_card.PaymentCardAccount')
    scheme_account = models.ForeignKey('scheme.SchemeAccount')

    class Meta:
        unique_together = ("payment_card_account", "scheme_account")


class SchemeAccountEntry(models.Model):
    scheme_account = models.ForeignKey('scheme.SchemeAccount')
    user = models.ForeignKey('user.CustomUser')

    class Meta:
        unique_together = ("scheme_account", "user")


class PaymentCardAccountEntry(models.Model):
    payment_card_account = models.ForeignKey('payment_card.PaymentCardAccount')
    user = models.ForeignKey('user.CustomUser')

    class Meta:
        unique_together = ("payment_card_account", "user")
