import logging
from typing import TYPE_CHECKING, Type, Union

import django
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError, models, transaction
from django.db.models import signals
from django.dispatch import receiver

from hermes.vop_tasks import send_deactivation, vop_activate_request
from history.signals import HISTORY_CONTEXT

if TYPE_CHECKING:
    from payment_card.models import PaymentCardAccount  # noqa
    from scheme.models import SchemeAccount  # noqa
    from user.models import CustomUser

logger = logging.getLogger(__name__)


class SchemeAccountEntry(models.Model):
    scheme_account = models.ForeignKey(
        "scheme.SchemeAccount", on_delete=models.CASCADE, verbose_name="Associated Scheme Account"
    )
    user = models.ForeignKey("user.CustomUser", on_delete=models.CASCADE, verbose_name="Associated User")
    auth_provided = models.BooleanField(default=False)

    class Meta:
        unique_together = ("scheme_account", "user")

    @staticmethod
    def create_link(user: "CustomUser", scheme_account: "SchemeAccount", auth_provided: bool) -> "SchemeAccountEntry":
        entry = SchemeAccountEntry(user=user, scheme_account=scheme_account, auth_provided=auth_provided)
        try:
            # required to rollback transactions when running into an expected IntegrityError
            # tests will fail without this as TestCase already wraps tests in an atomic
            # block and will not know how to correctly rollback otherwise
            with transaction.atomic():
                entry.save()
        except IntegrityError:
            # The id of the record is not currently required but if it is in the future then
            # we may need to use .get() here to retrieve the conflicting record.
            # An update is done here instead of initially using an update_or_create to avoid the db call
            # to check if a record exists, since this is an edge case.
            SchemeAccountEntry.objects.filter(user=user, scheme_account=scheme_account).update(
                auth_provided=auth_provided
            )

        return entry


class PaymentCardAccountEntry(models.Model):
    payment_card_account = models.ForeignKey(
        "payment_card.PaymentCardAccount", on_delete=models.CASCADE, verbose_name="Associated Payment Card Account"
    )
    user = models.ForeignKey("user.CustomUser", on_delete=models.CASCADE, verbose_name="Associated User")

    class Meta:
        unique_together = ("payment_card_account", "user")


class VopActivation(models.Model):
    ACTIVATING = 1
    DEACTIVATING = 2
    ACTIVATED = 3
    DEACTIVATED = 4

    VOP_STATUS = (
        (ACTIVATING, "activating"),
        (DEACTIVATING, "deactivating"),
        (ACTIVATED, "activated"),
        (DEACTIVATED, "deactivated"),
    )

    activation_id = models.CharField(null=True, blank=True, max_length=60)
    payment_card_account = models.ForeignKey(
        "payment_card.PaymentCardAccount", on_delete=models.PROTECT, verbose_name="Associated VOP Payment Card Account"
    )
    scheme = models.ForeignKey("scheme.Scheme", on_delete=models.PROTECT, verbose_name="Associated Scheme")
    status = models.IntegerField(choices=VOP_STATUS, default=1, help_text="Activation Status", db_index=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["payment_card_account", "scheme"], name="unique_activation")]

    @classmethod
    def find_activations_matching_links(cls, links):
        """Find activations matching links in the list"""
        activations = {}
        for link in links:
            try:
                activation = cls.objects.get(
                    payment_card_account_id=link.payment_card_account_id,
                    scheme_id=link.scheme_account.scheme_id,
                    status=cls.ACTIVATED,
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
    # General state of a PLL link
    PENDING = 0
    ACTIVE = 1
    INACTIVE = 2

    PLL_STATES = (
        (PENDING, "pending"),
        (ACTIVE, "active"),
        (INACTIVE, "inactive"),
    )

    # A more detailed status of a PLL Link
    LOYALTY_CARD_PENDING = "LOYALTY_CARD_PENDING"
    LOYALTY_CARD_NOT_AUTHORISED = "LOYALTY_CARD_NOT_AUTHORISED"
    PAYMENT_ACCOUNT_PENDING = "PAYMENT_ACCOUNT_PENDING"
    PAYMENT_ACCOUNT_INACTIVE = "PAYMENT_ACCOUNT_INACTIVE"
    PAYMENT_ACCOUNT_AND_LOYALTY_CARD_INACTIVE = "PAYMENT_ACCOUNT_AND_LOYALTY_CARD_INACTIVE"
    PAYMENT_ACCOUNT_AND_LOYALTY_CARD_PENDING = "PAYMENT_ACCOUNT_AND_LOYALTY_CARD_PENDING"
    UBIQUITY_COLLISION = "UBIQUITY_COLLISION"

    PLL_STATUSES = (
        (
            LOYALTY_CARD_PENDING,
            "LOYALTY_CARD_PENDING",
            "When the Loyalty Card becomes authorised, the PLL link will automatically go active.",
        ),
        (
            LOYALTY_CARD_NOT_AUTHORISED,
            "LOYALTY_CARD_NOT_AUTHORISED",
            "The Loyalty Card is not authorised so no PLL link can be created.",
        ),
        (
            PAYMENT_ACCOUNT_PENDING,
            "PAYMENT_ACCOUNT_PENDING",
            "When the Payment Account becomes active, the PLL link with automatically go active.",
        ),
        (
            PAYMENT_ACCOUNT_INACTIVE,
            "PAYMENT_ACCOUNT_INACTIVE",
            "The Payment Account is not active so no PLL link can be created.",
        ),
        (
            PAYMENT_ACCOUNT_AND_LOYALTY_CARD_INACTIVE,
            "PAYMENT_ACCOUNT_AND_LOYALTY_CARD_INACTIVE",
            "The Payment Account and Loyalty Card are not active/authorised so no PLL link can be created.",
        ),
        (
            PAYMENT_ACCOUNT_AND_LOYALTY_CARD_PENDING,
            "PAYMENT_ACCOUNT_AND_LOYALTY_CARD_PENDING",
            "When the Payment Account and the Loyalty Card become active/authorised, "
            "the PLL link with automatically go active.",
        ),
        (
            UBIQUITY_COLLISION,
            "UBIQUITY_COLLISION",
            "There is already a Loyalty Card from the same Loyalty Plan linked to this Payment Account.",
        ),
    )

    PLL_SLUGS = tuple(status[:2] for status in PLL_STATUSES)
    PLL_DESCRIPTIONS = tuple(status[::2] for status in PLL_STATUSES)

    payment_card_account = models.ForeignKey(
        "payment_card.PaymentCardAccount", on_delete=models.CASCADE, verbose_name="Associated Payment Card Account"
    )
    scheme_account = models.ForeignKey(
        "scheme.SchemeAccount", on_delete=models.CASCADE, verbose_name="Associated Membership Card Account"
    )
    active_link = models.BooleanField(default=False)
    state = models.IntegerField(default=PENDING, choices=PLL_STATES)
    slug = models.SlugField(blank=True, default="", choices=PLL_SLUGS)
    description = models.TextField(
        blank=True,
        default="",
        help_text="Short description of the PLL link status. This is automatically populated based on the slug.",
    )

    class Meta:
        unique_together = ("payment_card_account", "scheme_account")
        verbose_name = "Payment Card to Membership Card Association"
        verbose_name_plural = "".join([verbose_name, "s"])

    def save(self, *args, **kwargs):
        # This is to calculate and save the description when using the save method e.g saving via django admin.
        # This will not save the description for updates or bulk create/update methods.
        self.description = self.get_status_description()
        super().save(*args, **kwargs)

    @property
    def computed_active_link(self) -> bool:
        # a ubiquity collision is when an attempt is made to link a payment card to more than
        # one loyalty card of the same scheme
        if self.slug == self.UBIQUITY_COLLISION:
            collision = self._ubiquity_collision_check()
            if collision:
                self.state = self.INACTIVE
                self.description = self.get_status_description()
                return False

        if (
            not self.payment_card_account.is_deleted
            and not self.scheme_account.is_deleted
            and self.payment_card_account.status == self.payment_card_account.ACTIVE
            and self.scheme_account.status == self.scheme_account.ACTIVE
        ):
            self.state = self.ACTIVE
            self.slug = ""  # slugs are currently reserved to error states only
            self.description = self.get_status_description()
            return True

        self.set_status_slug()
        self.description = self.get_status_description()
        return False

    def set_status_slug(self):
        pcard_active = self.payment_card_account.status == self.payment_card_account.ACTIVE
        mcard_active = self.scheme_account.status == self.scheme_account.ACTIVE
        pcard_pending = self.payment_card_account.status == self.payment_card_account.PENDING
        mcard_pending = self.scheme_account.status == self.scheme_account.PENDING

        # These method calls should really be one if block but apparently that's too complex for the xenon check
        self._pending_check(pcard_active, pcard_pending, mcard_active, mcard_pending)
        self._inactive_check(pcard_active, pcard_pending, mcard_active, mcard_pending)

    def _pending_check(self, pcard_active: bool, mcard_active: bool, pcard_pending: bool, mcard_pending: bool) -> None:
        if pcard_pending and mcard_active:
            self.state = self.PENDING
            self.slug = self.PAYMENT_ACCOUNT_PENDING
        elif pcard_active and mcard_pending:
            self.state = self.PENDING
            self.slug = self.LOYALTY_CARD_PENDING
        elif pcard_pending and mcard_pending:
            self.state = self.PENDING
            self.slug = self.PAYMENT_ACCOUNT_AND_LOYALTY_CARD_PENDING

    def _inactive_check(self, pcard_active: bool, mcard_active: bool, pcard_pending: bool, mcard_pending: bool) -> None:
        if not pcard_active and not pcard_pending and (mcard_active or mcard_pending):
            self.state = self.INACTIVE
            self.slug = self.PAYMENT_ACCOUNT_INACTIVE
        elif not mcard_active and not mcard_pending and (pcard_active or pcard_pending):
            self.state = self.INACTIVE
            self.slug = self.LOYALTY_CARD_NOT_AUTHORISED
        else:
            self.state = self.INACTIVE
            self.slug = self.PAYMENT_ACCOUNT_AND_LOYALTY_CARD_INACTIVE

    def _ubiquity_collision_check(self) -> bool:
        scheme_accounts_count = (
            self.payment_card_account.scheme_account_set.filter(scheme=self.scheme_account.scheme_id)
            .exclude(pk=self.scheme_account_id)
            .count()
        )

        if scheme_accounts_count > 0:
            return True
        else:
            return False

    def get_status_description(self) -> str:
        try:
            if self.slug:
                return dict(self.PLL_DESCRIPTIONS)[self.slug]
            return ""
        except KeyError:
            raise ValueError(f'Invalid value set for "slug" property of PaymentCardSchemeEntry: "{self.slug}"')

    def vop_activate_check(self, prechecked=False):
        if prechecked or (self.payment_card_account.payment_card.slug == "visa" and self.active_link):
            # use get_or_create to ensure we avoid race conditions
            try:
                vop_activation, created = VopActivation.objects.get_or_create(
                    payment_card_account=self.payment_card_account,
                    scheme=self.scheme_account.scheme,
                    defaults={"activation_id": "", "status": VopActivation.ACTIVATING},
                )
                if (
                    created
                    or vop_activation.status == VopActivation.DEACTIVATED
                    or vop_activation.status == VopActivation.DEACTIVATING
                ):
                    vop_activate_request(vop_activation)

            except IntegrityError:
                logger.info(
                    "Ubiguity.models.PaymentCardSchemeEntry.vop_activate_check: integrity error prevented"
                    "- 2nd activation possible race condition, "
                    f" card_id: {self.payment_card_account.id} scheme: {self.scheme_account.scheme.id}"
                )

    def get_instance_with_active_status(self):
        """Returns the instance of its self after having first set the corrected active_link status
        :return: self
        """
        self.active_link = self.computed_active_link
        return self

    @classmethod
    def update_active_link_status(cls, query):
        links = cls.objects.filter(**query)
        logger.info("updating pll links of id: %s", [link.id for link in links])
        for link in links:
            old_active_link = link.active_link
            old_slug = link.slug
            updated_link = link.get_instance_with_active_status()
            try:
                if old_active_link != updated_link.active_link or old_slug != updated_link.slug:
                    logger.debug(
                        f"Link status for the link of id {updated_link.id} has changed from "
                        f'{{"active_link": "{old_active_link}", "slug": "{old_slug}"}} to '
                        f'{{"active_link": "{updated_link.active_link}", "slug": "{updated_link.slug}"}}'
                    )
                    updated_link.save(update_fields=["active_link", "state", "slug", "description"])
                    updated_link.vop_activate_check()
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
                active_link=True,
            ).count()
            if not matches and activation.status == VopActivation.ACTIVATED:
                try:
                    history_kwargs = {"user_info": HISTORY_CONTEXT.user_info}
                except AttributeError:
                    history_kwargs = None

                send_deactivation.delay(activation, history_kwargs)

    @classmethod
    def update_soft_links(cls, query):
        query["active_link"] = False
        cls.update_active_link_status(query)


def _remove_pll_link(instance: PaymentCardSchemeEntry) -> None:
    logger.info("payment card scheme entry of id %s has been deleted or deactivated", instance.id)

    def _remove_deleted_link_from_card(
        card_to_update: Union["PaymentCardAccount", "SchemeAccount"], linked_card_id: Type[int]
    ) -> None:
        model = card_to_update.__class__
        card_id = card_to_update.id
        existing_pll_links = model.all_objects.values_list("pll_links", flat=True).get(pk=card_id)
        logger.debug("checking pll links for %s of id %s", model.__name__, card_id)
        card_needs_update = False
        for i, link in enumerate(existing_pll_links):
            if link.get("id") == linked_card_id:
                del existing_pll_links[i]
                card_needs_update = True

        if card_needs_update:
            logger.debug("deleting link to %s", linked_card_id)
            model.objects.filter(pk=card_id).update(pll_links=existing_pll_links)

    _remove_deleted_link_from_card(instance.scheme_account, instance.payment_card_account_id)
    _remove_deleted_link_from_card(instance.payment_card_account, instance.scheme_account_id)


@receiver(signals.post_save, sender=PaymentCardSchemeEntry)
def update_pll_links_on_save(instance: PaymentCardSchemeEntry, created: bool, **kwargs) -> None:
    logger.info("payment card scheme entry of id %s updated", instance.id)
    if instance.active_link:

        def _add_new_link_to_card(
            card: Union["PaymentCardAccount", "SchemeAccount"], linked_card_id: Type[int]
        ) -> None:
            model = card.__class__
            card_id = card.id
            logger.debug("checking pll links for %s of id %s", model.__name__, card_id)
            existing_pll_links = model.objects.values_list("pll_links", flat=True).get(pk=card_id)
            if linked_card_id not in [link["id"] for link in existing_pll_links]:
                logger.debug("adding new link to %s", linked_card_id)
                existing_pll_links.append({"id": linked_card_id, "active_link": True})
                model.objects.filter(pk=card_id).update(pll_links=existing_pll_links)

        _add_new_link_to_card(instance.scheme_account, instance.payment_card_account_id)
        _add_new_link_to_card(instance.payment_card_account, instance.scheme_account_id)

    elif not created:
        _remove_pll_link(instance)


@receiver(signals.post_delete, sender=PaymentCardSchemeEntry)
def update_pll_links_on_delete(instance: PaymentCardSchemeEntry, **kwargs) -> None:
    _remove_pll_link(instance)


class ServiceConsent(models.Model):
    user = models.OneToOneField("user.CustomUser", on_delete=models.CASCADE, primary_key=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    timestamp = models.DateTimeField()


class MembershipPlanDocument(models.Model):
    scheme = models.ForeignKey("scheme.Scheme", on_delete=models.CASCADE, related_name="documents")
    name = models.CharField(max_length=150)
    description = models.CharField(max_length=500, blank=True)
    url = models.URLField(verbose_name="document")
    display = ArrayField(models.CharField(max_length=150))
    checkbox = models.BooleanField(verbose_name="needs checkbox")
    order = models.IntegerField(default=0)
