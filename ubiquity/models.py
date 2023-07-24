import json
import logging
import re
import sre_constants
from enum import Enum, IntEnum
from typing import TYPE_CHECKING, Iterable

from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError, models, transaction
from django.db.models import F, Q, signals
from django.dispatch import receiver
from django.utils.functional import cached_property

from hermes import settings
from hermes.vop_tasks import send_deactivation, vop_activate_request
from history.data_warehouse import user_pll_status_change_event
from history.signals import HISTORY_CONTEXT
from scheme.credentials import BARCODE, CARD_NUMBER, ENCRYPTED_CREDENTIALS, MERCHANT_IDENTIFIER, PASSWORD, PASSWORD_2
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
    link_status = models.IntegerField(default=AccountLinkStatus.PENDING, choices=AccountLinkStatus.statuses())
    authorised = models.BooleanField(default=False, verbose_name="User has been authorised.")

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
        user: "CustomUser", scheme_account: "SchemeAccount"
    ) -> tuple["SchemeAccountEntry", bool]:
        entry = SchemeAccountEntry(user=user, scheme_account=scheme_account)
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
        answers, card_number, barcode, merchant_identifier, alt_main_answer = self._answers_to_update()

        update_fields = []
        if card_number or barcode:
            self._update_barcode_and_card_number(card_number, answers=answers, primary_cred_type=CARD_NUMBER)
            self._update_barcode_and_card_number(barcode, answers=answers, primary_cred_type=BARCODE)
            update_fields.extend(["barcode", "card_number"])

        if alt_main_answer and alt_main_answer.answer != self.scheme_account.alt_main_answer:
            self.scheme_account.alt_main_answer = alt_main_answer.answer
            update_fields.append("alt_main_answer")

        if merchant_identifier and merchant_identifier.answer != self.scheme_account.merchant_identifier:
            self.scheme_account.merchant_identifier = merchant_identifier.answer
            update_fields.append("merchant_identifier")

        self.scheme_account.save(update_fields=update_fields)

    def _answers_to_update(
        self,
    ) -> tuple[
        set,
        "SchemeAccountCredentialAnswer",
        "SchemeAccountCredentialAnswer",
        "SchemeAccountCredentialAnswer",
        "SchemeAccountCredentialAnswer",
    ]:
        answers = {
            answer
            for answer in self.credential_answers
            if answer.question.manual_question or answer.question.scan_question or answer.question.one_question_link
            # This is in case a merchant sends back one of these key fields but they're not an add field
            # e.g squaremeal in a trusted channel. The fields still need populating since they could be
            # an add field in non-trusted channels.
            or answer.question.type in [CARD_NUMBER, BARCODE, MERCHANT_IDENTIFIER]
        }

        card_number = None
        barcode = None
        merchant_identifier = None
        alt_main_answer = None
        for answer in answers:
            if answer.question.type == CARD_NUMBER:
                card_number = answer
            elif answer.question.type == BARCODE:
                barcode = answer
            elif answer.question.type == MERCHANT_IDENTIFIER:
                merchant_identifier = answer
            else:
                alt_main_answer = answer

        return answers, card_number, barcode, merchant_identifier, alt_main_answer

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

    def set_link_status(self, new_status: "int | AccountLinkStatus", commit_change: bool = True) -> None:
        """
        Do not confuse the status of the scheme account set on the user association (link) and hence called
        link_status with pll linking status on  either PaymentCardSchemeEntry or  PllUserAssociation
        """
        new_status = int(new_status)
        if self.link_status == new_status:
            return

        self.link_status = new_status
        update_fields = ["link_status"]

        if self.link_status == AccountLinkStatus.ACTIVE and not self.authorised:
            self.authorised = True
            update_fields.append("authorised")

        if commit_change:
            self.save(update_fields=update_fields)

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


# todo: Replace all usages of Link statuses and slugs
#  This should be replaced again once these statuses have been moved to a shared library
class WalletPLLStatus(IntEnum):
    PENDING = 0
    ACTIVE = 1
    INACTIVE = 2

    @classmethod
    def get_states(cls) -> tuple:
        return (cls.PENDING.value, "pending"), (cls.ACTIVE.value, "active"), (cls.INACTIVE.value, "inactive")


class WalletPLLSlug(Enum):
    # A more detailed status of a PLL Link
    LOYALTY_CARD_PENDING = "LOYALTY_CARD_PENDING"
    LOYALTY_CARD_NOT_AUTHORISED = "LOYALTY_CARD_NOT_AUTHORISED"
    PAYMENT_ACCOUNT_PENDING = "PAYMENT_ACCOUNT_PENDING"
    PAYMENT_ACCOUNT_INACTIVE = "PAYMENT_ACCOUNT_INACTIVE"
    PAYMENT_ACCOUNT_AND_LOYALTY_CARD_INACTIVE = "PAYMENT_ACCOUNT_AND_LOYALTY_CARD_INACTIVE"
    PAYMENT_ACCOUNT_AND_LOYALTY_CARD_PENDING = "PAYMENT_ACCOUNT_AND_LOYALTY_CARD_PENDING"
    UBIQUITY_COLLISION = "UBIQUITY_COLLISION"

    @classmethod
    def get_descriptions(cls) -> tuple:
        return (
            (
                cls.LOYALTY_CARD_PENDING.value,
                "LOYALTY_CARD_PENDING",
                "When the Loyalty Card becomes authorised, the PLL link will automatically go active.",
            ),
            (
                cls.LOYALTY_CARD_NOT_AUTHORISED.value,
                "LOYALTY_CARD_NOT_AUTHORISED",
                "The Loyalty Card is not authorised so no PLL link can be created.",
            ),
            (
                cls.PAYMENT_ACCOUNT_PENDING.value,
                "PAYMENT_ACCOUNT_PENDING",
                "When the Payment Account becomes active, the PLL link with automatically go active.",
            ),
            (
                cls.PAYMENT_ACCOUNT_INACTIVE.value,
                "PAYMENT_ACCOUNT_INACTIVE",
                "The Payment Account is not active so no PLL link can be created.",
            ),
            (
                cls.PAYMENT_ACCOUNT_AND_LOYALTY_CARD_INACTIVE.value,
                "PAYMENT_ACCOUNT_AND_LOYALTY_CARD_INACTIVE",
                "The Payment Account and Loyalty Card are not active/authorised so no PLL link can be created.",
            ),
            (
                cls.PAYMENT_ACCOUNT_AND_LOYALTY_CARD_PENDING.value,
                "PAYMENT_ACCOUNT_AND_LOYALTY_CARD_PENDING",
                "When the Payment Account and the Loyalty Card become active/authorised, "
                "the PLL link with automatically go active.",
            ),
            (
                cls.UBIQUITY_COLLISION.value,
                "UBIQUITY_COLLISION",
                "There is already a Loyalty Card from the same Loyalty Plan linked to this Payment Account.",
            ),
        )

    @classmethod
    def get_status_map(cls) -> tuple:
        return (
            # Payment Card Account Active:  loyalty active, pending, inactive
            (
                (WalletPLLStatus.ACTIVE, ""),
                (WalletPLLStatus.PENDING, cls.LOYALTY_CARD_PENDING.value),
                (WalletPLLStatus.INACTIVE, cls.LOYALTY_CARD_NOT_AUTHORISED.value),
            ),
            # Payment Card Account Pending:  loyalty active, pending, inactive
            (
                (WalletPLLStatus.PENDING, cls.PAYMENT_ACCOUNT_PENDING.value),
                (WalletPLLStatus.PENDING, cls.PAYMENT_ACCOUNT_AND_LOYALTY_CARD_PENDING.value),
                (WalletPLLStatus.INACTIVE, cls.LOYALTY_CARD_NOT_AUTHORISED.value),
            ),
            # Payment Card Account inactive:  loyalty active, pending, inactive
            (
                (WalletPLLStatus.INACTIVE, cls.PAYMENT_ACCOUNT_INACTIVE.value),
                (WalletPLLStatus.INACTIVE, cls.PAYMENT_ACCOUNT_INACTIVE.value),
                (WalletPLLStatus.INACTIVE, cls.PAYMENT_ACCOUNT_AND_LOYALTY_CARD_INACTIVE.value),
            ),
        )


class WalletPLLData:
    def __init__(self, payment_card_account=None, scheme_account=None):
        """
        It is expected that the links passed will be
        :param links: query result or list of PllUserAssociations (wallet based PLL links)
        """
        self.to_query = True
        self.pll_user_associations = []
        if payment_card_account is not None and scheme_account is not None:
            # Finds all associations which refer to either the payment card account or scheme account for any user
            # Typical use is when a link is removed the status of any link using either the payment account or
            # scheme account might cause a change status or explanation for other links
            self.pll_user_associations = PllUserAssociation.objects.select_related(
                "pll__scheme_account", "pll__payment_card_account"
            ).filter(Q(pll__payment_card_account=payment_card_account) | Q(pll__scheme_account=scheme_account))
        elif payment_card_account is not None:
            self.pll_user_associations = PllUserAssociation.objects.select_related(
                "pll__scheme_account", "pll__payment_card_account"
            ).filter(pll__payment_card_account=payment_card_account)
        elif scheme_account is not None:
            self.pll_user_associations = PllUserAssociation.objects.select_related(
                "pll__scheme_account", "pll__payment_card_account"
            ).filter(pll__scheme_account=scheme_account)
        self.scheme_account_data = {}
        self.pll_data = {}
        self.scheme_count = {}
        self.link_users = {}
        self.included_payment_cards = {}

    def all(self) -> list["PllUserAssociation"]:
        for link in self.pll_user_associations:
            yield link

    def all_except_collision(self) -> list["PllUserAssociation"]:
        for link in self.pll_user_associations:
            if not self.collision(link):
                yield link

    def analyse_pll_user_associations(self):
        """
        Looks at user pll links to:
           1) creates a dict of links by link owner ie user id - used for finding scheme entries for related users and
              parsing the relevant links by wallet
           2) creates a dict of scheme counts by payment account and scheme id - used to detect ubiquity collision
              assuming the user links include all links related to either a payment card account or scheme account
              or both  (see __init__ queries ie this class requires either or both accounts)

        """
        self.link_users = {}
        self.scheme_account_data = {}
        self.scheme_count = {}
        self.included_payment_cards = {}
        for link in self.pll_user_associations:
            if self.included_payment_cards.get(link.pll.payment_card_account_id):
                self.included_payment_cards[link.pll.payment_card_account_id].append(link)
            else:
                self.included_payment_cards[link.pll.payment_card_account_id] = [link]

        included_pll_user_associations = PllUserAssociation.objects.select_related(
            "pll__scheme_account", "pll__payment_card_account"
        ).filter(pll__payment_card_account__in=list(self.included_payment_cards.keys()))

        for link in included_pll_user_associations:
            if self.link_users.get(link.user_id):
                self.link_users[link.user_id].append(link)
            else:
                self.link_users[link.user_id] = [link]
            scheme_id = link.pll.scheme_account.scheme_id
            pay_id = link.pll.payment_card_account_id
            if not self.scheme_count.get(pay_id):
                self.scheme_count[pay_id] = {}
            if self.scheme_count[pay_id].get(scheme_id):
                self.scheme_count[pay_id][scheme_id] += 1
            else:
                self.scheme_count[pay_id][scheme_id] = 1

    def process_links(self):
        if self.to_query:
            # Only reads db when first called and prepares a dict of the pll relationships and status using
            # results of 2 queries merged assuming that an account is unique in a wallet.
            # The object is to avoid multiple calls to the database and all class methods to be called repeatedly
            #
            self.to_query = False
            self.analyse_pll_user_associations()

            scheme_entries = SchemeAccountEntry.objects.filter(user_id__in=list(self.link_users.keys()))
            for entry in scheme_entries:
                for lk in self.link_users[entry.user_id]:
                    if lk.pll.scheme_account_id == entry.scheme_account_id:
                        matched_link = lk

                        pay_id = matched_link.pll.payment_card_account_id
                        scheme_id = matched_link.pll.scheme_account.scheme_id
                        if not self.scheme_account_data.get(entry.scheme_account_id):
                            self.scheme_account_data[entry.scheme_account_id] = {}
                        self.scheme_account_data[entry.scheme_account_id][entry.user_id] = {
                            "status": entry.link_status,
                            "link": matched_link,
                            "scheme_count": self.scheme_count[pay_id][scheme_id],
                        }

    def get_link_data(self, link: "PllUserAssociation") -> dict[str, "str | int | PllUserAssociation | None"]:
        default_link_data = {"status": None, "link": None, "scheme_count": 0}
        self.process_links()
        sas = self.scheme_account_data.get(link.pll.scheme_account.id)
        if sas:
            sa = sas.get(link.user_id, default_link_data)
            return sa
        return default_link_data

    def scheme_account_status(self, link: "PllUserAssociation"):
        data = self.get_link_data(link)
        return data.get("status")

    def collision(self, link: "PllUserAssociation"):
        data = self.get_link_data(link)
        scheme_more_than_once = data.get("scheme_count", 0) > 1

        # if the link slug is not marked as collision it must be the link before the collision occurred so false
        if data.get("link") and data["link"].slug != WalletPLLSlug.UBIQUITY_COLLISION.value and scheme_more_than_once:
            return False
        # returns true for other scheme linked more than once to a payment card and false otherwise even if slug
        # says it was a collision
        return scheme_more_than_once


class PllUserAssociation(models.Model):
    """
    This model represents the user's wallet view of PLL
    It has a many-to-many relationship to PaymentCardSchemeEntry.

    PaymentCardSchemeEntry is in effect is the actual PLL relationship between a payment AND scheme accounts
    ie Harmonia processes all active links.

    Because a user's wallet may have shared Payment and Scheme accounts with different status this view of PLL
    is a user's view of the link showing status and description slug
    """

    # General state of a PLL link
    PLL_DESCRIPTIONS = tuple(status[::2] for status in WalletPLLSlug.get_descriptions())
    PLL_SLUG_CHOICE = tuple(status[:2] for status in WalletPLLSlug.get_descriptions())

    state = models.IntegerField(default=WalletPLLStatus.PENDING.value, choices=WalletPLLStatus.get_states())
    slug = models.SlugField(blank=True, default="", choices=PLL_SLUG_CHOICE)
    pll = models.ForeignKey(
        "PaymentCardSchemeEntry", default=None, on_delete=models.CASCADE, verbose_name="Associated PLL"
    )
    user = models.ForeignKey("user.CustomUser", on_delete=models.CASCADE, verbose_name="Associated User")
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("pll", "user")

    @classmethod
    def get_pll_previous_state_and_slug(cls, created: bool, user_link: "PllUserAssociation") -> tuple[str, int]:
        previous_slug = ""
        previous_state = None

        if not created:
            previous_slug = user_link.slug
            previous_state = user_link.state

        return previous_slug, previous_state

    @classmethod
    def get_state_and_slug(cls, payment_card_account: "PaymentCardAccount", scheme_account_status: int):
        pay_index = 2
        scheme_index = 2
        account_pending = (
            AccountLinkStatus.PENDING,
            AccountLinkStatus.AUTH_PENDING,
            AccountLinkStatus.ADD_AUTH_PENDING,
            AccountLinkStatus.JOIN_ASYNC_IN_PROGRESS,
            AccountLinkStatus.JOIN_IN_PROGRESS,
            AccountLinkStatus.REGISTRATION_ASYNC_IN_PROGRESS,
        )
        if payment_card_account.status == payment_card_account.ACTIVE:
            pay_index = 0
        elif payment_card_account.status == payment_card_account.PENDING:
            pay_index = 1
        if scheme_account_status == AccountLinkStatus.ACTIVE:
            scheme_index = 0
        elif scheme_account_status in account_pending:
            scheme_index = 1
        status_map = WalletPLLSlug.get_status_map()
        return status_map[pay_index][scheme_index]

    @classmethod
    def get_slug_description(cls, slug: WalletPLLSlug) -> str:
        try:
            if slug:
                return dict(cls.PLL_DESCRIPTIONS)[slug]
            return ""
        except KeyError:
            raise ValueError(f'Invalid slug value: "{slug}" sent to PllUserAssociation.get_slug_description')

    @staticmethod
    def update_link(link: "PllUserAssociation", wallet_pll_records: list["PllUserAssociation"]):
        link.save()
        if link.state == WalletPLLStatus.ACTIVE:
            # Set the generic pll link to active if not already set
            if not link.pll.active_link:
                link.pll.activate()

        else:
            update_base_link = True
            for pll in wallet_pll_records:
                if pll.state == WalletPLLStatus.ACTIVE:
                    update_base_link = False
                    break

            if update_base_link:
                link.pll.active_link = False
                link.pll.save()

    @classmethod
    def update_user_pll_by_both(
        cls, payment_card_account: "PaymentCardAccount", scheme_account: "SchemeAccount", headers: dict = None
    ):
        wallet_pll_data = WalletPLLData(payment_card_account=payment_card_account, scheme_account=scheme_account)
        # these are pll user links to all wallets which have this payment_card_account
        wallet_pll_records = wallet_pll_data.all_except_collision()
        for link in wallet_pll_data.all_except_collision():
            previous_state = link.state
            previous_slug = link.slug

            link.state, link.slug = cls.get_state_and_slug(
                link.pll.payment_card_account, wallet_pll_data.scheme_account_status(link)
            )
            cls.update_link(link, wallet_pll_records)

            user_pll_status_change_event(link, previous_slug, previous_state, headers)

    @classmethod
    def update_user_pll_by_pay_account(cls, payment_card_account: "PaymentCardAccount", headers: dict = None):
        wallet_pll_data = WalletPLLData(payment_card_account=payment_card_account)
        # these are pll user links to all wallets which have this payment_card_account
        wallet_pll_records = wallet_pll_data.all_except_collision()
        for link in wallet_pll_data.all_except_collision():
            previous_state = link.state
            previous_slug = link.slug

            link.state, link.slug = cls.get_state_and_slug(
                link.pll.payment_card_account, wallet_pll_data.scheme_account_status(link)
            )
            cls.update_link(link, wallet_pll_records)

            logger.info("Sending pll_link.statuschange event from payment account.")
            user_pll_status_change_event(link, previous_slug, previous_state, headers)

    @classmethod
    def update_user_pll_by_scheme_account(cls, scheme_account: "SchemeAccount"):
        wallet_pll_data = WalletPLLData(scheme_account=scheme_account)
        # these are pll user links to all wallets which have this scheme_account
        wallet_pll_records = wallet_pll_data.all_except_collision()
        for link in wallet_pll_data.all_except_collision():
            previous_state = link.state
            previous_slug = link.slug

            wallet_scheme_account_status = wallet_pll_data.scheme_account_status(link)
            link.state, link.slug = cls.get_state_and_slug(link.pll.payment_card_account, wallet_scheme_account_status)
            cls.update_link(link, wallet_pll_records)

            logger.info("Sending pll_link.statuschange event from scheme account.")
            user_pll_status_change_event(link, previous_slug, previous_state)

    @classmethod
    def link_users_scheme_accounts(
        cls,
        payment_card_account: "PaymentCardAccount",
        scheme_account_entries: list["SchemeAccountEntry"],
        headers: dict = None,
    ):
        for scheme_account_entry in scheme_account_entries:
            cls.link_users_scheme_account_entry_to_payment(scheme_account_entry, payment_card_account, headers)

    @classmethod
    def link_user_scheme_account_to_payment_cards(
        cls,
        scheme_account: "SchemeAccount",
        payment_card_accounts: list["PaymentCardAccount"],
        user: "CustomUser",
        headers: dict = None,
    ):
        scheme_user_entry = SchemeAccountEntry.objects.select_related("scheme_account").get(
            user=user, scheme_account=scheme_account, scheme_account__is_deleted=False
        )
        cls.link_users_payment_cards(scheme_user_entry, payment_card_accounts, headers)

    @classmethod
    def link_users_payment_cards(
        cls,
        scheme_account_entry: SchemeAccountEntry,
        payment_card_accounts: list["PaymentCardAccount"],
        headers: dict = None,
    ):
        for payment_card_account in payment_card_accounts:
            if isinstance(payment_card_account, int):  # In background tasks a list of ids is sent rather than objects
                from payment_card.models import PaymentCardAccount  # need to avoid circular import

                payment_card_account = PaymentCardAccount.objects.get(id=payment_card_account)
            cls.link_users_scheme_account_entry_to_payment(scheme_account_entry, payment_card_account, headers=headers)

    @classmethod
    def link_users_scheme_account_to_payment(
        cls, scheme_account: "SchemeAccount", payment_card_account: "PaymentCardAccount", user: "CustomUser"
    ) -> "PllUserAssociation":
        scheme_user_entry = SchemeAccountEntry.objects.select_related("scheme_account").get(
            user=user, scheme_account=scheme_account, scheme_account__is_deleted=False
        )
        return cls.link_users_scheme_account_entry_to_payment(scheme_user_entry, payment_card_account)

    @classmethod
    def link_users_scheme_account_entry_to_payment(
        cls, scheme_account_entry: SchemeAccountEntry, payment_card_account: "PaymentCardAccount", headers: dict = None
    ) -> "PllUserAssociation":
        """
        This is called after a new scheme account entry or payment card is created and a user PLL
        link and base link must be created.

        Ubiquity collision will be set if payment card is base linked to scheme account who's scheme
        has been used elsewhere.

        Unlike the update methods this does not need to unset Ubiquity collision as it is for new PLL relationships

        """
        scheme_account = scheme_account_entry.scheme_account
        user = scheme_account_entry.user
        status, slug = cls.get_state_and_slug(payment_card_account, scheme_account_entry.link_status)
        base_status = False
        if status == WalletPLLStatus.ACTIVE:
            base_status = True
        scheme_count = (
            payment_card_account.scheme_account_set.filter(scheme=scheme_account.scheme_id)
            .exclude(pk=scheme_account.id)
            .count()
        )

        if scheme_count > 0:
            status = WalletPLLStatus.INACTIVE
            slug = WalletPLLSlug.UBIQUITY_COLLISION.value
            base_status = False

        base_link, base_created = PaymentCardSchemeEntry.objects.get_or_create(
            payment_card_account=payment_card_account,
            scheme_account=scheme_account,
            defaults={"active_link": base_status},
        )

        if base_status:
            # activate if not been done already
            if not base_link.active_link:
                base_link.activate(save=True)
            elif base_created:
                base_link.activate(save=False)

        # Check if in multi wallet
        # If base link is already active do not update unless it's a single wallet scenario
        if cls.objects.filter(pll=base_link).count() < 1:
            if base_link.active_link != base_status:
                base_link.active_link = base_status
                base_link.save()

        user_link, link_created = cls.objects.get_or_create(
            pll=base_link, user=user, defaults={"slug": slug, "state": status}
        )

        previous_slug, previous_state = cls.get_pll_previous_state_and_slug(link_created, user_link)

        # update existing user link but don't change if had a UBIQUITY_COLLISION
        if not link_created and user_link.slug != WalletPLLSlug.UBIQUITY_COLLISION.value:
            user_link.status = status
            user_link.slug = slug
            user_link.save()

        user_pll_status_change_event(user_link, previous_slug, previous_state, headers)

        return user_link


class PaymentCardSchemeEntry(models.Model):
    payment_card_account = models.ForeignKey(
        "payment_card.PaymentCardAccount", on_delete=models.CASCADE, verbose_name="Associated Payment Card Account"
    )
    scheme_account = models.ForeignKey(
        "scheme.SchemeAccount", on_delete=models.CASCADE, verbose_name="Associated Membership Card Account"
    )
    active_link = models.BooleanField(default=False)

    class Meta:
        unique_together = ("payment_card_account", "scheme_account")
        verbose_name = "Payment Card to Membership Card Association"
        verbose_name_plural = "".join([verbose_name, "s"])

    def __str__(self):
        return (
            f"PaymentCardSchemeEntry id: {self.id} - "
            f"PaymentCardAccount id: {self.payment_card_account.id} - "
            f"SchemeAccount id: {self.scheme_account.id}"
        )

    def activate(self, save: bool = True):
        """
        This activates a link - we should be always call this to activate a link for PLL
        and ensure VOP activations are applied
        Note: this is the base PLL level the user's PLL status wallet may be different
        @ todo should we update the pll links in associated payment cards and scheme accounts?
        :return:
        """
        if save:
            self.active_link = True
            self.save()
        self.vop_activate_check()

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

    @classmethod
    def deactivate_activations(cls, activations: dict, headers: dict = None):
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

                send_deactivation.delay(activation, history_kwargs, headers)

    # @todo pll stuff remove methods below this line -----------------------------------


"""
    def set_active_link_status(self, scheme_account_status: bool = False) -> object:
        Returns the instance of its self after having first set the corrected active_link status
        Allows request to be chained as self is returned
        :return: self
        if (
            not self.payment_card_account.is_deleted
            and not self.scheme_account.is_deleted
            and self.payment_card_account.status == self.payment_card_account.ACTIVE
            and scheme_account_status
        ):
            self.active_link = True
        else:
            self.active_link = False
        return self
"""
"""
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
"""
"""
    # @todo pll stuff remove this method
    def set_status_slug(self):
        pcard_active = self.payment_card_account.status == self.payment_card_account.ACTIVE
        mcard_active = self.scheme_account.status == self.scheme_account.ACTIVE
        pcard_pending = self.payment_card_account.status == self.payment_card_account.PENDING
        mcard_pending = self.scheme_account.status == self.scheme_account.PENDING

        # These method calls should really be one if block but apparently that's too complex for the xenon check

        self._inactive_check(pcard_active, mcard_active, pcard_pending, mcard_pending)
        self._pending_check(pcard_active, mcard_active, pcard_pending, mcard_pending)
"""
"""
    # @todo pll stuff remove this method
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
"""
"""
    # @todo pll stuff remove this method
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
"""
"""
    # @todo pll stuff remove this method
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
"""
"""
    # @todo pll stuff remove this method
    def get_status_description(self) -> str:
        try:
            if self.slug:
                return dict(self.PLL_DESCRIPTIONS)[self.slug]
            return ""
        except KeyError:
            raise ValueError(f'Invalid value set for "slug" property of PaymentCardSchemeEntry: "{self.slug}"')
"""
"""
    # @todo pll stuff remove this method
    def get_instance_with_active_status(self):
        # Returns the instance of its self after having first set the corrected active_link status
        # :return: self
        self.active_link = self.computed_active_link
        return self
"""
"""
    # @todo pll stuff remove this method
    @classmethod
    def update_active_link_status(cls, query):
        This is really a bit back to front ie it will be a method on PllUserAssociation
        update_user_pll_by_pay
        update_user_pll_by_scheme

        rather than the basic link but doing it this way for compatibility
        with API 1.x and existing code.
        links = cls.objects.filter(**query)
        logger.info("updating pll links of id: %s", [link.id for link in links])
        # These links are between the payment and scheme accounts so we need to find the
        # associate user and update PllUserAssociation
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
"""
"""
    # @todo pll stuff remove this method
    @classmethod
    def update_soft_links(cls, query):
        query["active_link"] = False
        cls.update_active_link_status(query)
"""


def _remove_pll_link(instance: PaymentCardSchemeEntry) -> None:
    logger.info("payment card scheme entry of id %s has been deleted or deactivated", instance.id)

    def _remove_deleted_link_from_card(
        card_to_update: "PaymentCardAccount | SchemeAccount", linked_card_id: type[int]
    ) -> None:
        model = card_to_update.__class__
        card_id = card_to_update.id
        existing_pll_links = model.all_objects.values_list("pll_links", flat=True).get(pk=card_id)
        logger.debug("checking pll links for %s of id %s", model.__name__, card_id)
        card_needs_update = False

        if existing_pll_links:
            for i, link in enumerate(existing_pll_links):
                if link.get("id") == linked_card_id:
                    del existing_pll_links[i]
                    card_needs_update = True

        if card_needs_update:
            model.objects.filter(pk=card_id).update(pll_links=existing_pll_links)
            logger.debug(f"Updated {model.__name__}(id={card_id}) pll_links - deleted link to {linked_card_id}")

    _remove_deleted_link_from_card(instance.scheme_account, instance.payment_card_account_id)
    _remove_deleted_link_from_card(instance.payment_card_account, instance.scheme_account_id)


@receiver(signals.post_save, sender=PaymentCardSchemeEntry)
def update_pll_links_on_save(instance: PaymentCardSchemeEntry, created: bool, **kwargs) -> None:
    logger.info("payment card scheme entry of id %s updated", instance.id)
    if instance.active_link:

        def _add_new_link_to_card(card: "PaymentCardAccount | SchemeAccount", linked_card_id: type[int]) -> None:
            model = card.__class__
            card_id = card.id
            logger.debug("checking pll links for %s of id %s", model.__name__, card_id)
            existing_pll_links = model.objects.values_list("pll_links", flat=True).get(pk=card_id)
            if linked_card_id not in [link["id"] for link in existing_pll_links]:
                existing_pll_links.append({"id": linked_card_id, "active_link": True})
                model.objects.filter(pk=card_id).update(pll_links=existing_pll_links)
                logger.debug(f"Updated {model.__name__}(id={card_id}) pll_links - added new link to {linked_card_id}")

        _add_new_link_to_card(instance.scheme_account, instance.payment_card_account_id)
        _add_new_link_to_card(instance.payment_card_account, instance.scheme_account_id)

    elif not created:
        _remove_pll_link(instance)


@receiver(signals.post_delete, sender=PaymentCardSchemeEntry)
def update_pll_links_on_delete(instance: PaymentCardSchemeEntry, **kwargs) -> None:
    PllUserAssociation.objects.filter(pll=instance).delete()
    PllUserAssociation.update_user_pll_by_both(instance.payment_card_account, instance.scheme_account)
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
