import json
import logging
import re
import sre_constants
from typing import TYPE_CHECKING, Iterable, Type, Union

import django
from hermes import settings
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError, models, transaction
from django.db.models import F, signals
from django.dispatch import receiver
from django.utils.functional import cached_property

from analytics.api import update_scheme_account_attribute_new_status
from hermes.vop_tasks import send_deactivation, vop_activate_request
from history.signals import HISTORY_CONTEXT
from scheme.credentials import BARCODE, CARD_NUMBER, ENCRYPTED_CREDENTIALS, PASSWORD, PASSWORD_2
from scheme.encryption import AESCipher
from ubiquity.channel_vault import AESKeyNames

if TYPE_CHECKING:
    from payment_card.models import PaymentCardAccount  # noqa
    from scheme.models import SchemeAccount  # noqa
    from scheme.models import SchemeAccountCredentialAnswer
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

    @cached_property
    def credential_answers(self):
        return self.schemeaccountcredentialanswer_set.filter(
            question__scheme_id=self.scheme_account.scheme_id
        ).select_related("question")

    @staticmethod
    def create_or_retrieve_link(
        user: "CustomUser", scheme_account: "SchemeAccount", auth_provided: bool
    ) -> tuple(("SchemeAccountEntry", bool)):
        entry = SchemeAccountEntry(user=user, scheme_account=scheme_account, auth_provided=auth_provided)
        created = True
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
            created = False

        return entry, created

    def update_or_create_primary_credentials(self, credentials):
        """
        Creates or updates scheme account credential answer objects for manual or scan questions. If only one is
        given and the scheme has a regex conversion for the property, both will be saved.
        :param credentials: dict of credentials
        :return: credentials
        """
        new_credentials = {
            question["type"]: credentials.get(question["type"])
            for question in self.scheme_account.scheme.get_required_questions
        }

        for k, v in new_credentials.items():
            if v:
                SchemeAccountCredentialAnswer.objects.update_or_create(
                    question=self.scheme_account.question(k),
                    scheme_account=self.scheme_account,
                    scheme_account_entry=self,
                    defaults={"answer": v},
                )

        self.update_barcode_and_card_number()
        for question in ["card_number", "barcode"]:
            value = getattr(self, question)
            if not credentials.get(question) and value:
                credentials.update({question: value})

        return credentials

    def update_barcode_and_card_number(self):

        answers = {answer for answer in self.credential_answers if answer.question.type in [CARD_NUMBER, BARCODE]}

        card_number = None
        barcode = None
        for answer in answers:
            if answer.question.type == CARD_NUMBER:
                card_number = answer
            elif answer.question.type == BARCODE:
                barcode = answer

        self._update_barcode_and_card_number(card_number, answers=answers, primary_cred_type=CARD_NUMBER)
        self._update_barcode_and_card_number(barcode, answers=answers, primary_cred_type=BARCODE)

        self.scheme_account.save(update_fields=["barcode", "card_number"])

    def _update_barcode_and_card_number(
        self,
        primary_cred: "SchemeAccountCredentialAnswer",
        answers: Iterable["SchemeAccountCredentialAnswer"],
        primary_cred_type: str,
    ) -> None:
        """
        Updates the given primary credential of either card number or barcode. The non-provided (secondary)
        credential is also updated if the conversion regex exists for the scheme.
        """
        if not answers:
            setattr(self.scheme_account, primary_cred_type, "")
            return

        if not primary_cred:
            return

        type_to_update_info = {
            CARD_NUMBER: {
                "regex": self.scheme_account.scheme.barcode_regex,
                "prefix": self.scheme_account.scheme.barcode_prefix,
                "secondary_cred_type": BARCODE,
            },
            BARCODE: {
                "regex": self.scheme_account.scheme.card_number_regex,
                "prefix": self.scheme_account.scheme.card_number_prefix,
                "secondary_cred_type": CARD_NUMBER,
            },
        }

        setattr(self.scheme_account, primary_cred_type, primary_cred.answer)

        if type_to_update_info[primary_cred_type]["regex"]:
            try:
                regex_match = re.search(type_to_update_info[primary_cred_type]["regex"], primary_cred.answer)
            except sre_constants.error:
                setattr(self.scheme_account, type_to_update_info[primary_cred_type]["secondary_cred_type"], "")
                return None
            if regex_match:
                try:
                    setattr(
                        self.scheme_account,
                        type_to_update_info[primary_cred_type]["secondary_cred_type"],
                        type_to_update_info[primary_cred_type]["prefix"] + regex_match.group(1),
                    )
                except IndexError:
                    pass

    def missing_credentials(self, credential_types):
        """
        Given a list of credential_types return credentials if they are required by the scheme

        A scan or manual question is an optional if one of the other exists
        """
        from scheme.models import SchemeCredentialQuestion

        questions = self.scheme_account.scheme.questions.filter(
            options__in=[F("options").bitor(SchemeCredentialQuestion.LINK), SchemeCredentialQuestion.NONE]
        )

        required_credentials = {question.type for question in questions}
        manual_question = self.scheme_account.scheme.manual_question
        scan_question = self.scheme_account.scheme.scan_question

        if manual_question:
            required_credentials.add(manual_question.type)
        if scan_question:
            required_credentials.add(scan_question.type)

        if scan_question and manual_question and scan_question != manual_question:
            if scan_question.type in credential_types:
                required_credentials.discard(manual_question.type)
            if required_credentials and manual_question.type in credential_types:
                required_credentials.discard(scan_question.type)

        return required_credentials.difference(set(credential_types))

    def credentials(self, credentials_override: dict = None):

        credentials = self._collect_credential_answers()

        if self.scheme_account.scheme.slug != "iceland-bonus-card":
            if self._iceland_hack(credentials, credentials_override):
                return None

        for credential in credentials.keys():
            # Other services only expect a single password, "password", so "password_2" must be converted
            # before sending if it exists. Ideally, the new credential would be handled in the consuming
            # service and this should be removed.
            if credential == PASSWORD_2:
                credentials[PASSWORD] = credentials.pop(credential)

        saved_consents = self.scheme_account.collect_pending_consents()
        credentials.update(consents=saved_consents)

        if credentials_override:
            credentials.update(credentials_override)

        serialized_credentials = json.dumps(credentials)
        return AESCipher(AESKeyNames.AES_KEY).encrypt(serialized_credentials).decode("utf-8")

    def _collect_credential_answers(self):
        credentials = {}
        for question in self.scheme_account.scheme.questions.all():
            # attempt to get the answer from the database.
            answer = self._find_answer(question)

            if not answer:
                continue

            if question.type in ENCRYPTED_CREDENTIALS:
                credentials[question.type] = AESCipher(AESKeyNames.LOCAL_AES_KEY).decrypt(answer)
            else:
                credentials[question.type] = answer
        return credentials

    def _find_answer(self, question):
        answer = None
        answer_instance = self.schemeaccountcredentialanswer_set.filter(question__type=question.type).first()
        if answer_instance:
            answer = answer_instance.answer
        else:
            # see if we have a property that will give us the answer.
            try:
                answer = getattr(self, question.type)
            except AttributeError:
                # we can't get an answer to this question, so skip it.
                pass
        return answer

    def _iceland_hack(self, credentials: dict = None, credentials_override: dict = None) -> bool:
        # todo: we will need to review this for P2

        if self.scheme_account in self.scheme_account.ALL_PENDING_STATUSES:
            return False

        missing = self.missing_credentials(credentials.keys())

        if missing and not credentials_override:
            bink_users = [user for user in self.scheme_account.user_set.all() if user.client_id == settings.BINK_CLIENT_ID]
            for user in bink_users:
                update_scheme_account_attribute_new_status(
                    self.scheme_account, user, dict(self.scheme_account.STATUSES).get(self.scheme_account.INCOMPLETE)
                )
            self.status = self.scheme_account.INCOMPLETE
            self.save()
            return True  # triggers return None from calling method
        return False


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

        self._inactive_check(pcard_active, mcard_active, pcard_pending, mcard_pending)
        self._pending_check(pcard_active, mcard_active, pcard_pending, mcard_pending)

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
        if not pcard_active and (mcard_active or mcard_pending):
            self.state = self.INACTIVE
            self.slug = self.PAYMENT_ACCOUNT_INACTIVE
        elif not mcard_active and (pcard_active or pcard_pending):
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
