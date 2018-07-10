from django.db import models


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


class PaymentCardSchemeEntry(models.Model):
    payment_card_account = models.ForeignKey('payment_card.PaymentCardAccount')
    scheme_account = models.ForeignKey('scheme.SchemeAccount')
    active_link = models.BooleanField(default=True)

    class Meta:
        unique_together = ("payment_card_account", "scheme_account")

    def activate_link(self):
        account_links = self.__class__.objects.filter(
            payment_card_account=self.payment_card_account, scheme_account__scheme=self.scheme_account.scheme
        ).exclude(pk=self.pk)
        account_links.update(active_link=False)

        if not self.active_link:
            self.active_link = True
            self.save()

        return account_links.all()


class ServiceConsent(models.Model):
    user = models.OneToOneField('user.CustomUser', on_delete=models.CASCADE, primary_key=True)
    latitude = models.FloatField()
    longitude = models.FloatField()
    timestamp = models.DateTimeField()
