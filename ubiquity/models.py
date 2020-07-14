from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models import signals
from django.dispatch import receiver


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
        same_scheme_links = self.__class__.objects.filter(
            payment_card_account=self.payment_card_account, scheme_account__scheme=self.scheme_account.scheme
        ).exclude(pk=self.pk)

        # The autolink rule is to choose the oldest link over current one but for now we will prefer the one requested
        # and delete the older ones
        # todo check if we should use the autolink selection and also prefer active links

        same_scheme_links.delete()
        called_status = self.active_link
        self.active_link = self.computed_active_link
        if called_status != self.active_link:
            self.save()

    @property
    def computed_active_link(self):
        if self.payment_card_account.status == self.payment_card_account.ACTIVE and \
                not self.payment_card_account.is_deleted and \
                self.scheme_account.status == self.scheme_account.ACTIVE and \
                not self.scheme_account.is_deleted:
            return True
        return False

    def get_instance_with_active_status(self):
        """ Returns the instance of its self after having first set the corrected active_link status
        :return: self
        """
        self.active_link = self.computed_active_link
        return self

    @classmethod
    def update_active_link_status(cls, query):
        links = cls.objects.filter(**query)
        bulk_update = []
        for link in links:
            current_state = link.active_link
            update_link = link.get_instance_with_active_status()
            if current_state != update_link.active_link:
                bulk_update.append(update_link)
        if bulk_update:
            cls.objects.bulk_update(bulk_update, ['active_link'])

    @classmethod
    def update_soft_links(cls, query):
        query['active_link'] = False
        cls.update_active_link_status(query)


def _remove_pll_link(instance: PaymentCardSchemeEntry):
    mcard = instance.scheme_account
    mcard_needs_update = False
    for i, link in enumerate(mcard.pll_links):
        if link['id'] == instance.payment_card_account_id:
            mcard.pll_links.pop(i)
            mcard_needs_update = True

    pcard = instance.payment_card_account
    pcard_needs_update = False
    for i, link in enumerate(pcard.pll_links):
        if link['id'] == instance.scheme_account_id:
            pcard.pll_links.pop(i)
            pcard_needs_update = True

    if mcard_needs_update:
        mcard.save(update_fields=['pll_links'])
    if pcard_needs_update:
        pcard.save(update_fields=['pll_links'])


@receiver(signals.post_save, sender=PaymentCardSchemeEntry)
def update_pll_links_on_save(sender, instance, created, **kwargs):
    if instance.active_link:
        mcard = instance.scheme_account
        if instance.payment_card_account_id not in [link['id'] for link in mcard.pll_links]:
            mcard.pll_links.append({'id': instance.payment_card_account_id, 'active_link': instance.active_link})
            mcard.save(update_fields=['pll_links'])

        pcard = instance.payment_card_account
        if instance.scheme_account_id not in [link['id'] for link in pcard.pll_links]:
            pcard.pll_links.append({'id': instance.scheme_account_id, 'active_link': instance.active_link})
            pcard.save(update_fields=['pll_links'])

    elif not created:
        _remove_pll_link(instance)


@receiver(signals.post_delete, sender=PaymentCardSchemeEntry)
def update_pll_links_on_delete(sender, instance, **kwargs):
    if instance.active_link:
        _remove_pll_link(instance)


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
