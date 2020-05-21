from django.contrib.postgres.fields import ArrayField
from django.db import models


class SchemeAccountEntry(models.Model):
    scheme_account = models.ForeignKey('scheme.SchemeAccount', on_delete=models.CASCADE,
                                       verbose_name="Associated Scheme Account")
    user = models.ForeignKey('user.CustomUser', on_delete=models.CASCADE, verbose_name="Associated User")

    class Meta:
        unique_together = ("scheme_account", "user")


class PaymentCardAccountEntry(models.Model):
    payment_card_account = models.ForeignKey('payment_card.PaymentCardAccount', on_delete=models.CASCADE,
                                             verbose_name="Associated Payment Card Account")
    user = models.ForeignKey('user.CustomUser', on_delete=models.CASCADE, verbose_name="Associated User")

    class Meta:
        unique_together = ("payment_card_account", "user")


class PaymentCardSchemeEntry(models.Model):
    UNDEFINED = 0
    ACTIVATING = 1
    DEACTIVATING = 2
    ACTIVATED = 3

    VOP_STATUS = (
        (UNDEFINED, 'undefined'),
        (ACTIVATING, 'activating'),
        (DEACTIVATING, 'deactivating'),
        (ACTIVATED, 'activated')
    )

    payment_card_account = models.ForeignKey('payment_card.PaymentCardAccount', on_delete=models.CASCADE,
                                             verbose_name="Associated Payment Card Account")
    scheme_account = models.ForeignKey('scheme.SchemeAccount', on_delete=models.CASCADE,
                                       verbose_name="Associated Membership Card Account")
    active_link = models.BooleanField(default=False)
    vop_link = models.IntegerField(choices=VOP_STATUS, default=0, help_text='The status of VOP card activation')

    class Meta:
        unique_together = ("payment_card_account", "scheme_account")
        verbose_name = "Payment Card to Membership Card Association"
        verbose_name_plural = "".join([verbose_name, 's'])

    def activate_link(self):
        account_links = self.__class__.objects.filter(
            payment_card_account=self.payment_card_account, scheme_account__scheme=self.scheme_account.scheme
        ).exclude(pk=self.pk)
        account_links.update(active_link=False)
        #@todo Soft Link set Active only if both  payment card and membership card are active otherwise false
        if not self.active_link:
            self.active_link = True
            self.save()

        return account_links.all()

    def get_active_status(self):
        if self.payment_card_account.status == self.payment_card_account.ACTIVE and \
                not self.payment_card_account.is_deleted and \
                self.scheme_account.status == self.scheme_account.ACTIVE and \
                not self.scheme_account.is_deleted:
            return True
        return False

    def set_active_status(self):
        self.active_link = self.get_active_status()


class ServiceConsent(models.Model):
    user = models.OneToOneField('user.CustomUser', on_delete=models.CASCADE, primary_key=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    timestamp = models.DateTimeField()


class MembershipPlanDocument(models.Model):
    scheme = models.ForeignKey('scheme.Scheme', on_delete=models.CASCADE, related_name='documents')
    name = models.CharField(max_length=150)
    description = models.CharField(max_length=500, blank=True)
    url = models.URLField(verbose_name='document')
    display = ArrayField(models.CharField(max_length=150))
    checkbox = models.BooleanField(verbose_name='needs checkbox')
