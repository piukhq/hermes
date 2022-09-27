import json
import logging
import re
import sre_constants
from enum import IntEnum
from typing import TYPE_CHECKING, Iterable, Type, Union

import django
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError, models, transaction
from django.db.models import F, signals
from django.dispatch import receiver
from django.utils.functional import cached_property

from hermes import settings
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


# todo: Replace all usages of SchemeAccount statuses with this and delete from SchemeAccount.
#  This should be replaced again once these statuses have been moved to a shared library
class AccountLinkStatus(IntEnum):
    PENDING = 0
    ACTIVE = 1
    INVALID_CREDENTIALS = 403
    INVALID_MFA = 432
    END_SITE_DOWN = 530
    IP_BLOCKED = 531
    TRIPPED_CAPTCHA = 532
    INCOMPLETE = 5
    LOCKED_BY_ENDSITE = 434
    RETRY_LIMIT_REACHED = 429
    RESOURCE_LIMIT_REACHED = 503
    UNKNOWN_ERROR = 520
    MIDAS_UNREACHABLE = 9
    AGENT_NOT_FOUND = 404
    WALLET_ONLY = 10
    PASSWORD_EXPIRED = 533
    JOIN = 900
    NO_SUCH_RECORD = 444
    CONFIGURATION_ERROR = 536
    NOT_SENT = 535
    ACCOUNT_ALREADY_EXISTS = 445
    SERVICE_CONNECTION_ERROR = 537
    VALIDATION_ERROR = 401
    PRE_REGISTERED_CARD = 406
    FAILED_UPDATE = 446
    SCHEME_REQUESTED_DELETE = 447
    PENDING_MANUAL_CHECK = 204
    CARD_NUMBER_ERROR = 436
    LINK_LIMIT_EXCEEDED = 437
    CARD_NOT_REGISTERED = 438
    GENERAL_ERROR = 439
    JOIN_IN_PROGRESS = 441
    JOIN_ERROR = 538
    JOIN_ASYNC_IN_PROGRESS = 442
    REGISTRATION_ASYNC_IN_PROGRESS = 443
    ENROL_FAILED = 901
    REGISTRATION_FAILED = 902
    JOIN_FAILED = 903
    AUTHORISATION_FAILED = 904
    ADD_AUTH_PENDING = 1001
    AUTH_PENDING = 2001

    @classmethod
    def extended_statuses(cls):
        return (
            (cls.PENDING.value, "Pending", "PENDING"),
            (cls.ACTIVE.value, "Active", "ACTIVE"),
            (cls.INVALID_CREDENTIALS.value, "Invalid credentials", "INVALID_CREDENTIALS"),
            (cls.INVALID_MFA.value, "Invalid mfa", "INVALID_MFA"),
            (cls.END_SITE_DOWN.value, "End site down", "END_SITE_DOWN"),
            (cls.IP_BLOCKED.value, "IP blocked", "IP_BLOCKED"),
            (cls.TRIPPED_CAPTCHA.value, "Tripped captcha", "TRIPPED_CAPTCHA"),
            (cls.INCOMPLETE.value, "Please check your scheme account login details.", "INCOMPLETE"),
            (cls.LOCKED_BY_ENDSITE.value, "Account locked on end site", "LOCKED_BY_ENDSITE"),
            (cls.RETRY_LIMIT_REACHED.value, "Cannot connect, too many retries", "RETRY_LIMIT_REACHED"),
            (cls.RESOURCE_LIMIT_REACHED.value, "Too many balance requests running", "RESOURCE_LIMIT_REACHED"),
            (cls.UNKNOWN_ERROR.value, "An unknown error has occurred", "UNKNOWN_ERROR"),
            (cls.MIDAS_UNREACHABLE.value, "Midas unavailable", "MIDAS_UNREACHABLE"),
            (cls.WALLET_ONLY.value, "Wallet only card", "WALLET_ONLY"),
            (cls.AGENT_NOT_FOUND.value, "Agent does not exist on midas", "AGENT_NOT_FOUND"),
            (cls.PASSWORD_EXPIRED.value, "Password expired", "PASSWORD_EXPIRED"),
            (cls.JOIN.value, "Join", "JOIN"),
            (cls.NO_SUCH_RECORD.value, "No user currently found", "NO_SUCH_RECORD"),
            (
                cls.CONFIGURATION_ERROR.value,
                "Error with the configuration or it was not possible to retrieve",
                "CONFIGURATION_ERROR",
            ),
            (cls.NOT_SENT.value, "Request was not sent", "NOT_SENT"),
            (cls.ACCOUNT_ALREADY_EXISTS.value, "Account already exists", "ACCOUNT_ALREADY_EXISTS"),
            (cls.SERVICE_CONNECTION_ERROR.value, "Service connection error", "SERVICE_CONNECTION_ERROR"),
            (cls.VALIDATION_ERROR.value, "Failed validation", "VALIDATION_ERROR"),
            (cls.PRE_REGISTERED_CARD.value, "Pre-registered card", "PRE_REGISTERED_CARD"),
            (cls.FAILED_UPDATE.value, "Update failed. Delete and re-add card.", "FAILED_UPDATE"),
            (cls.PENDING_MANUAL_CHECK.value, "Pending manual check.", "PENDING_MANUAL_CHECK"),
            (cls.CARD_NUMBER_ERROR.value, "Invalid card_number", "CARD_NUMBER_ERROR"),
            (cls.LINK_LIMIT_EXCEEDED.value, "You can only Link one card per day.", "LINK_LIMIT_EXCEEDED"),
            (cls.CARD_NOT_REGISTERED.value, "Unknown Card number", "CARD_NOT_REGISTERED"),
            (cls.GENERAL_ERROR.value, "General Error such as incorrect user details", "GENERAL_ERROR"),
            (cls.JOIN_IN_PROGRESS.value, "Join in progress", "JOIN_IN_PROGRESS"),
            (cls.JOIN_ERROR.value, "A system error occurred during join", "JOIN_ERROR"),
            (
                cls.SCHEME_REQUESTED_DELETE.value,
                "The scheme has requested this account should be deleted",
                "SCHEME_REQUESTED_DELETE",
            ),
            (cls.JOIN_ASYNC_IN_PROGRESS.value, "Asynchronous join in progress", "JOIN_ASYNC_IN_PROGRESS"),
            (
                cls.REGISTRATION_ASYNC_IN_PROGRESS.value,
                "Asynchronous registration in progress",
                "REGISTRATION_ASYNC_IN_PROGRESS",
            ),
            (cls.ENROL_FAILED.value, "Enrol Failed", "ENROL_FAILED"),
            (cls.REGISTRATION_FAILED.value, "Ghost Card Registration Failed", "REGISTRATION_FAILED"),
            (cls.JOIN_FAILED, "JoinFailed", "JOIN_FAILED"),
            (cls.AUTHORISATION_FAILED, "AuthorisationFailed", "AUTHORISATION_FAILED"),
            (cls.ADD_AUTH_PENDING.value, "Add and Auth pending", "ADD_AUTH_PENDING"),
            (cls.AUTH_PENDING.value, "Auth pending", "AUTH_PENDING"),
        )

    @classmethod
    def statuses(cls):
        return tuple(extended_status[:2] for extended_status in AccountLinkStatus.extended_statuses())

    @classmethod
    def join_action_required(cls):
        return [
            cls.JOIN,
            cls.CARD_NOT_REGISTERED,
            cls.PRE_REGISTERED_CARD,
            cls.REGISTRATION_FAILED,
            cls.ENROL_FAILED,
            cls.ACCOUNT_ALREADY_EXISTS,
        ]

    @classmethod
    def user_action_required(cls):
        return [
            cls.INVALID_CREDENTIALS,
            cls.INVALID_MFA,
            cls.INCOMPLETE,
            cls.LOCKED_BY_ENDSITE,
            cls.VALIDATION_ERROR,
            cls.PRE_REGISTERED_CARD,
            cls.REGISTRATION_FAILED,
            cls.CARD_NUMBER_ERROR,
            cls.GENERAL_ERROR,
            cls.JOIN_IN_PROGRESS,
            cls.SCHEME_REQUESTED_DELETE,
            cls.FAILED_UPDATE,
        ]

    @classmethod
    def system_action_required(cls):
        return [
            cls.END_SITE_DOWN,
            cls.RETRY_LIMIT_REACHED,
            cls.UNKNOWN_ERROR,
            cls.MIDAS_UNREACHABLE,
            cls.IP_BLOCKED,
            cls.TRIPPED_CAPTCHA,
            cls.RESOURCE_LIMIT_REACHED,
            cls.LINK_LIMIT_EXCEEDED,
            cls.CONFIGURATION_ERROR,
            cls.NOT_SENT,
            cls.SERVICE_CONNECTION_ERROR,
            cls.JOIN_ERROR,
            cls.AGENT_NOT_FOUND,
        ]

    @classmethod
    def exclude_balance_statuses(cls):
        return (
            cls.join_action_required()
            + cls.user_action_required()
            + [cls.PENDING, cls.PENDING_MANUAL_CHECK, cls.WALLET_ONLY, cls.ADD_AUTH_PENDING, cls.AUTH_PENDING]
        )

    @classmethod
    def join_exclude_balance_statuses(cls):
        return [
            cls.PENDING_MANUAL_CHECK,
            cls.JOIN,
            cls.JOIN_ASYNC_IN_PROGRESS,
            cls.REGISTRATION_ASYNC_IN_PROGRESS,
            cls.ENROL_FAILED,
        ]

    @classmethod
    def join_pending(cls):
        return [cls.JOIN_ASYNC_IN_PROGRESS]

    @classmethod
    def register_pending(cls):
        return [cls.REGISTRATION_ASYNC_IN_PROGRESS]

    @classmethod
    def pre_pending_statuses(cls):
        return [cls.AUTH_PENDING, cls.ADD_AUTH_PENDING]

    @classmethod
    def all_pending_statuses(cls):
        return [cls.PENDING, cls.AUTH_PENDING, cls.ADD_AUTH_PENDING]


class SchemeAccountEntry(models.Model):
    scheme_account = models.ForeignKey(
        "scheme.SchemeAccount", on_delete=models.CASCADE, verbose_name="Associated Scheme Account"
    )
    user = models.ForeignKey("user.CustomUser", on_delete=models.CASCADE, verbose_name="Associated User")
    auth_provided = models.BooleanField(default=False)
    link_status = models.IntegerField(default=AccountLinkStatus.PENDING, choices=AccountLinkStatus.statuses())

    class Meta:
        unique_together = ("scheme_account", "user")

    @property
    def status_name(self):
        return dict(AccountLinkStatus.statuses()).get(self.link_status)

    @property
    def status_key(self):
        status_keys = dict(
            (extended_status[0], extended_status[2]) for extended_status in AccountLinkStatus.extended_statuses()
        )
        return status_keys.get(self.link_status)

    @property
    def display_status(self):
        # linked accounts in "system account required" should be displayed as "active".
        # accounts in "active", "pending", and "join" statuses should be displayed as such.
        # all other statuses should be displayed as "wallet only"
        if (
            self.scheme_account.link_date or self.scheme_account.join_date
        ) and self.link_status in AccountLinkStatus.system_action_required():
            return AccountLinkStatus.ACTIVE
        elif self.link_status in [AccountLinkStatus.ACTIVE, AccountLinkStatus.PENDING, AccountLinkStatus.JOIN]:
            return self.link_status
        elif self.link_status in AccountLinkStatus.join_action_required():
            return AccountLinkStatus.JOIN
        else:
            return AccountLinkStatus.WALLET_ONLY

    @cached_property
    def credential_answers(self):
        return self.schemeaccountcredentialanswer_set.filter(
            question__scheme_id=self.scheme_account.scheme_id
        ).select_related("question")

    @staticmethod
    def create_or_retrieve_link(
        user: "CustomUser", scheme_account: "SchemeAccount", auth_provided: bool
    ) -> tuple["SchemeAccountEntry", bool]:
        entry = SchemeAccountEntry(user=user, scheme_account=scheme_account, auth_provided=auth_provided)
        created = True
        try:
            # required to rollback transactions when running into an expected IntegrityError
            # tests will fail without this as TestCase already wraps tests in an atomic
            # block and will not know how to correctly rollback otherwise
            with transaction.atomic():
                entry.save()
        except IntegrityError:
            # An update is done here instead of initially using an update_or_create to avoid the db call
            # to check if a record exists, since this is an edge case.
            entry = SchemeAccountEntry.objects.get(user=user, scheme_account=scheme_account)
            entry.auth_provided = auth_provided
            entry.save(update_fields=["auth_provided"])
            created = False

        return entry, created

    def update_or_create_primary_credentials(self, credentials):
        """
        Creates or updates scheme account credential answer objects for manual or scan questions. If only one is
        given and the scheme has a regex conversion for the property, both will be saved.
        :param credentials: dict of credentials
        :return: credentials
        """
        from scheme.models import SchemeAccountCredentialAnswer

        new_credentials = {
            question["type"]: credentials.get(question["type"])
            for question in self.scheme_account.scheme.get_required_questions
        }

        for k, v in new_credentials.items():
            if v:
                SchemeAccountCredentialAnswer.objects.update_or_create(
                    question=self.scheme_account.question(k),
                    scheme_account_entry=self,
                    defaults={"answer": v},
                )

        self.update_scheme_account_key_credential_fields()

        for question in ["card_number", "barcode"]:
            value = getattr(self.scheme_account, question)
            if not credentials.get(question) and value:
                credentials.update({question: value})

        return credentials

    def update_scheme_account_key_credential_fields(self) -> None:
        """
        Updates the main answer fields on the scheme account (card_number, barcode, alt_main_answer) based on
        the SchemeAccountCredentialAnswers linked to the SchemeAccountEntry. By default, this will not update
        an existing value to an empty value if the user does not have the credential saved.
        """
        answers = {
            answer
            for answer in self.credential_answers
            if answer.question.manual_question or answer.question.scan_question or answer.question.one_question_link
        }

        card_number = None
        barcode = None
        for answer in answers:
            if answer.question.type == CARD_NUMBER:
                card_number = answer
            elif answer.question.type == BARCODE:
                barcode = answer

        if answers:
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

    def set_link_status(self, new_status: int, commit_change=True):
        if self.auth_provided is True:
            status_to_set = new_status
        else:
            status_to_set = AccountLinkStatus.WALLET_ONLY

        self.link_status = status_to_set
        if commit_change:
            self.save(update_fields=["link_status"])

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
        """
        Returns all credentials for this scheme_account_entry as an encoded string. The 'main_answer' credential's value
         is replaced with the main_answer value from the Scheme Account. This is to avoid problems of different
         account-identifying information between different users.
        """

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

        if credentials_override:
            credentials.update(credentials_override)

        saved_consents = self.scheme_account.collect_pending_consents()
        credentials.update(consents=saved_consents)

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

    @property
    def third_party_identifier(self):
        from scheme.models import SchemeCredentialQuestion

        question = SchemeCredentialQuestion.objects.filter(
            third_party_identifier=True, scheme=self.scheme_account.scheme
        ).first()
        if question:
            return self._find_answer(question)

        return None

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

        if self.link_status in AccountLinkStatus.all_pending_statuses():
            return False

        missing = self.missing_credentials(credentials.keys())

        if missing and not credentials_override and self.user.client_id == settings.BINK_CLIENT_ID:
            self.set_link_status(AccountLinkStatus.INCOMPLETE)
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

    def active_scheme_in_any_wallet(self):
        for entry in self.scheme_account.schemeaccountentry_set.all():
            if entry.link_status == AccountLinkStatus.ACTIVE:
                return True
        return False

    @property
    def computed_active_link(self) -> bool:
        # todo: Check PLL changes - this needs consider status of all scheme_account_entries
        #
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
            and self.active_scheme_in_any_wallet()
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
