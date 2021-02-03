import logging
from typing import Union, Type, TYPE_CHECKING

import django
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError, models
from django.db.models import signals
from django.dispatch import receiver

from hermes.vop_tasks import vop_activate_request, send_deactivation
from history.signals import HISTORY_CONTEXT

if TYPE_CHECKING:
    from scheme.models import SchemeAccount  # noqa
    from payment_card.models import PaymentCardAccount  # noqa

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
    status = models.IntegerField(choices=VOP_STATUS, default=1, help_text='Activation Status', db_index=True)

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

    # @classmethod
    # def deactivation_dict_by_payment_card_id(cls, payment_card_account_id, status=ACTIVATED):
    #     """Find activations matching account id and return a serializable object"""
    #     activation_dict = {}
    #
    #     activations = cls.objects.filter(
    #             payment_card_account_id=payment_card_account_id,
    #             status=status
    #     )
    #
    #     for activation in activations:
    #         activation_id = activation.activation_id
    #         activation_dict[activation.id] = {
    #             'scheme': activation.scheme.slug,
    #             'activation_id': activation_id
    #         }
    #         activation.status = VopActivation.DEACTIVATING
    #
    #     history_bulk_update(VopActivation, activations, update_fields=["status"])
    #
    #     return activation_dict


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

    def vop_activate_check(self, prechecked=False):
        if prechecked or (self.payment_card_account.payment_card.slug == "visa" and self.active_link):
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
        logger.info("updating pll links of id: %s", [link.id for link in links])
        for link in links:
            current_state = link.active_link
            update_link = link.get_instance_with_active_status()
            try:
                if current_state != update_link.active_link:
                    logger.debug(
                        "active_link for the link of id %s has changed to %s", update_link.id, update_link.active_link
                    )
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
                history_kwargs = {"user_info": HISTORY_CONTEXT.user_info}
                send_deactivation.delay(activation, history_kwargs)

    @classmethod
    def update_soft_links(cls, query):
        query['active_link'] = False
        cls.update_active_link_status(query)


def _remove_pll_link(instance: PaymentCardSchemeEntry) -> None:
    logger.info('payment card scheme entry of id %s has been deleted or deactivated', instance.id)

    def _remove_deleted_link_from_card(
            card_to_update: Union['PaymentCardAccount', 'SchemeAccount'],
            linked_card_id: Type[int]
    ) -> None:
        model = card_to_update.__class__
        card_id = card_to_update.id
        existing_pll_links = model.all_objects.values_list('pll_links', flat=True).get(pk=card_id)
        logger.debug('checking pll links for %s of id %s', model.__name__, card_id)
        card_needs_update = False
        for i, link in enumerate(existing_pll_links):
            if link.get('id') == linked_card_id:
                del existing_pll_links[i]
                card_needs_update = True

        if card_needs_update:
            logger.debug('deleting link to %s', linked_card_id)
            model.objects.filter(pk=card_id).update(pll_links=existing_pll_links)

    _remove_deleted_link_from_card(instance.scheme_account, instance.payment_card_account_id)
    _remove_deleted_link_from_card(instance.payment_card_account, instance.scheme_account_id)


@receiver(signals.post_save, sender=PaymentCardSchemeEntry)
def update_pll_links_on_save(instance: PaymentCardSchemeEntry, created: bool, **kwargs) -> None:
    logger.info('payment card scheme entry of id %s updated', instance.id)
    if instance.active_link:

        def _add_new_link_to_card(
                card: Union['PaymentCardAccount', 'SchemeAccount'],
                linked_card_id: Type[int]
        ) -> None:
            model = card.__class__
            card_id = card.id
            logger.debug('checking pll links for %s of id %s', model.__name__, card_id)
            existing_pll_links = model.objects.values_list('pll_links', flat=True).get(pk=card_id)
            if linked_card_id not in [link['id'] for link in existing_pll_links]:
                logger.debug('adding new link to %s', linked_card_id)
                existing_pll_links.append({'id': linked_card_id, 'active_link': True})
                model.objects.filter(pk=card_id).update(pll_links=existing_pll_links)

        _add_new_link_to_card(instance.scheme_account, instance.payment_card_account_id)
        _add_new_link_to_card(instance.payment_card_account, instance.scheme_account_id)

    elif not created:
        _remove_pll_link(instance)


@receiver(signals.post_delete, sender=PaymentCardSchemeEntry)
def update_pll_links_on_delete(instance: PaymentCardSchemeEntry, **kwargs) -> None:
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
