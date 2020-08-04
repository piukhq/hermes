import logging

from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError
from django.db import models
from django.db.models import signals
from django.dispatch import receiver
from hermes.vop_tasks import vop_activate_request, send_deactivation

logger = logging.getLogger(__name__)


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


class VopActivation(models.Model):
    ACTIVATING = 1
    DEACTIVATING = 2
    ACTIVATED = 3
    DEACTIVATED = 4

    VOP_STATUS = (
        (ACTIVATING, 'activating'),
        (DEACTIVATING, 'deactivating'),
        (ACTIVATED, 'activated'),
        (DEACTIVATED, 'deactivated'),
    )

    activation_id = models.CharField(null=True, blank=True, max_length=60)
    payment_card_account = models.ForeignKey('payment_card.PaymentCardAccount', on_delete=models.PROTECT,
                                             verbose_name="Associated VOP Payment Card Account")
    scheme = models.ForeignKey('scheme.Scheme', on_delete=models.PROTECT, verbose_name="Associated Scheme")
    status = models.IntegerField(choices=VOP_STATUS, default=1, help_text='Activation Status')

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['payment_card_account', 'scheme'], name='unique_activation')
        ]

    @classmethod
    def find_activations_matching_links(cls, links):
        """Find activations matching links in the list"""
        activations = {}
        for link in links:
            try:
                activation = cls.objects.get(
                    payment_card_account=link.payment_card_account,
                    scheme=link.scheme_account.scheme,
                    status=cls.ACTIVATED
                )
                activations[activation.id] = activation
            except ObjectDoesNotExist:
                pass
        return activations



class PaymentCardSchemeEntry(models.Model):

    payment_card_account = models.ForeignKey('payment_card.PaymentCardAccount', on_delete=models.CASCADE,
                                             verbose_name="Associated Payment Card Account")
    scheme_account = models.ForeignKey('scheme.SchemeAccount', on_delete=models.CASCADE,
                                       verbose_name="Associated Membership Card Account")
    active_link = models.BooleanField(default=False)

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
            self.vop_activate_check()

    @property
    def computed_active_link(self):
        if self.payment_card_account.status == self.payment_card_account.ACTIVE and \
                not self.payment_card_account.is_deleted and \
                self.scheme_account.status == self.scheme_account.ACTIVE and \
                not self.scheme_account.is_deleted:
            return True
        return False

    def vop_activate_check(self):
        if self.payment_card_account.payment_card.slug == "visa" and self.active_link:
            # use get_or_create to ensure we avoid race conditions
            try:
                vop_activation, created = VopActivation.objects.get_or_create(
                    payment_card_account=self.payment_card_account,
                    scheme=self.scheme_account.scheme,
                    defaults={'activation_id': "", "status": VopActivation.ACTIVATING}
                )
                if created or vop_activation.status == VopActivation.DEACTIVATED\
                        or vop_activation.status == VopActivation.DEACTIVATING:
                    vop_activate_request(vop_activation)

            except IntegrityError:
                logger.info(f'Ubiguity.models.PaymentCardSchemeEntry.vop_activate_check: integrity error prevented'
                            f'- 2nd activation possible race condition, '
                            f' card_id: {self.payment_card_account.id} scheme: {self.scheme_account.scheme.id}')

    def get_instance_with_active_status(self):
        """ Returns the instance of its self after having first set the corrected active_link status
        :return: self
        """
        self.active_link = self.computed_active_link
        return self

    @classmethod
    def update_active_link_status(cls, query):
        links = cls.objects.filter(**query)
        for link in links:
            current_state = link.active_link
            update_link = link.get_instance_with_active_status()
            if current_state != update_link.active_link:
                update_link.save(update_fields=['active_link'])
                update_link.vop_activate_check()

    @classmethod
    def deactivate_activations(cls, activations: dict):
        """If an activation cannot be supported by an active link then deactivate it if activated"""
        for activation in activations.values():
            # check if any entries require the activation - deactivate if not used
            matches = cls.objects.filter(
                payment_card_account=activation.payment_card_account,
                scheme_account__scheme=activation.scheme,
                active_link=True
            ).count()
            if not matches and activation.status == VopActivation.ACTIVATED:
                send_deactivation.delay(activation)

    @classmethod
    def update_soft_links(cls, query):
        query['active_link'] = False
        cls.update_active_link_status(query)


def _remove_pll_link(instance: PaymentCardSchemeEntry):
    mcard = instance.scheme_account
    mcard_needs_update = False
    for i, link in enumerate(mcard.pll_links):
        if link['id'] == instance.payment_card_account_id:
            del mcard.pll_links[i]
            mcard_needs_update = True

    pcard = instance.payment_card_account
    pcard_needs_update = False
    for i, link in enumerate(pcard.pll_links):
        if link['id'] == instance.scheme_account_id:
            del pcard.pll_links[i]
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
