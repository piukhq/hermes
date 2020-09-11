import logging

import django
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError, models
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
                    payment_card_account_id=link.payment_card_account_id,
                    scheme_id=link.scheme_account.scheme_id,
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
                if created or vop_activation.status == VopActivation.DEACTIVATED \
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
            try:
                if current_state != update_link.active_link:
                    update_link.save(update_fields=['active_link'])
                    update_link.vop_activate_check()
            except django.db.utils.DatabaseError:
                # Handles race condition for when updating a link that has been deleted
                pass

    @classmethod
    def deactivate_activations(cls, activations: dict):
        """If an activation cannot be supported by an active link then deactivate it if activated"""
        for activation in activations.values():
            # check if any entries require the activation - deactivate if not used
            matches = cls.objects.filter(
                payment_card_account_id=activation.payment_card_account_id,
                scheme_account__scheme_id=activation.scheme_id,
                active_link=True
            ).count()
            if not matches and activation.status == VopActivation.ACTIVATED:
                send_deactivation.delay(activation)

    @classmethod
    def update_soft_links(cls, query):
        query['active_link'] = False
        cls.update_active_link_status(query)


def _remove_pll_link(instance: PaymentCardSchemeEntry):
    def _remove_deleted_link_from_card(card_to_update, linked_card_id):
        card_to_update.refresh_from_db(fields=['pll_links'])
        card_needs_update = False
        for i, link in enumerate(card_to_update.pll_links):
            if link['id'] == linked_card_id:
                del card_to_update.pll_links[i]
                card_needs_update = True

        if card_needs_update:
            card_to_update.save(update_fields=['pll_links'])

    _remove_deleted_link_from_card(instance.scheme_account, instance.payment_card_account_id)
    _remove_deleted_link_from_card(instance.payment_card_account, instance.scheme_account)


@receiver(signals.post_save, sender=PaymentCardSchemeEntry)
def update_pll_links_on_save(instance, created, **kwargs):
    if instance.active_link:
        def _add_new_link_to_card(card_to_update, linked_card_id):
            card_to_update.refresh_from_db(fields=['pll_links'])
            if linked_card_id not in [link['id'] for link in card_to_update.pll_links]:
                card_to_update.pll_links.append({'id': linked_card_id, 'active_link': True})
                card_to_update.save(update_fields=['pll_links'])

        _add_new_link_to_card(instance.scheme_account, instance.payment_card_account_id)
        _add_new_link_to_card(instance.payment_card_account, instance.scheme_account)

    elif not created:
        _remove_pll_link(instance)


@receiver(signals.post_delete, sender=PaymentCardSchemeEntry)
def update_pll_links_on_delete(instance, **kwargs):
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
