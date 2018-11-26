from django.db import models


class SchemeAccountEntry(models.Model):
    scheme_account = models.ForeignKey('scheme.SchemeAccount', on_delete=models.CASCADE,
                                       verbose_name="scheme association")
    user = models.ForeignKey('user.CustomUser', on_delete=models.CASCADE, verbose_name="user email")

    class Meta:
        unique_together = ("scheme_account", "user")


class PaymentCardAccountEntry(models.Model):
    payment_card_account = models.ForeignKey('payment_card.PaymentCardAccount', on_delete=models.CASCADE,
                                             verbose_name="Payment Card User association")
    user = models.ForeignKey('user.CustomUser', on_delete=models.CASCADE, verbose_name="user email")

    class Meta:
        unique_together = ("payment_card_account", "user")


class PaymentCardSchemeEntry(models.Model):
    payment_card_account = models.ForeignKey('payment_card.PaymentCardAccount', on_delete=models.CASCADE)
    scheme_account = models.ForeignKey('scheme.SchemeAccount', on_delete=models.CASCADE)
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
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    timestamp = models.DateTimeField()
