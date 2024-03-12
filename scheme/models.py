import logging
import re
import socket
import sre_constants
import uuid
from collections.abc import Iterable
from decimal import ROUND_HALF_UP, Decimal
from enum import IntEnum
from typing import TYPE_CHECKING

import arrow
import requests
from bulk_update.manager import BulkUpdateManager
from colorful.fields import RGBColorField
from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.db.models import F, JSONField, Q, UniqueConstraint, signals
from django.dispatch import receiver
from django.template.defaultfilters import truncatewords
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from common.models import Image
from prometheus.utils import capture_membership_card_status_change_metric
from scheme import vouchers
from scheme.credentials import BARCODE, CARD_NUMBER, CREDENTIAL_TYPES, ENCRYPTED_CREDENTIALS
from scheme.encryption import AESCipher
from scheme.vouchers import VoucherStateStr
from ubiquity.channel_vault import AESKeyNames
from ubiquity.models import AccountLinkStatus, SchemeAccountEntry
from ubiquity.reason_codes import REASON_CODES

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from user.models import ClientApplication

logger = logging.getLogger(__name__)

BARCODE_TYPES = (
    (0, "CODE128 (B or C)"),
    (1, "QrCode"),
    (2, "AztecCode"),
    (3, "Pdf417"),
    (4, "EAN (13)"),
    (5, "DataMatrix"),
    (6, "ITF (Interleaved 2 of 5)"),
    (7, "Code 39"),
)


slug_regex = re.compile(r"^[a-z0-9\-]+$")
hex_colour_re = re.compile("^#((?:[0-9a-fA-F]{3}){1,2})$")
validate_hex_colour = RegexValidator(hex_colour_re, _("Enter a valid 'colour' in hexadecimal format e.g \"#112233\""))


class UbiquityBalanceHandler:
    point_info = None
    value_info = None
    data = None
    precision = None

    def __init__(self, dictionary):
        if isinstance(dictionary, list):
            dictionary, *_ = dictionary

        if "scheme_id" in dictionary:
            self._collect_scheme_balances_info(dictionary["scheme_id"])

        self.point_balance = dictionary.get("points")
        self.value_balance = dictionary.get("value")
        self.updated_at = dictionary.get("updated_at")
        self.reward_tier = dictionary.get("reward_tier", 0)
        self._get_balances()

    def _collect_scheme_balances_info(self, scheme_id):
        for balance_info in SchemeBalanceDetails.objects.filter(scheme_id=scheme_id).all():
            # Set info for points or known currencies and also set precision for each supported currency
            if balance_info.currency in ["GBP", "EUR", "USD"]:
                self.value_info = balance_info
                self.precision = Decimal("0.01")
            else:
                self.point_info = balance_info

    def _format_balance(self, value, info, is_currency):
        """
        :param value:
        :type value: float, int, string or Decimal
        :param info:
        :type info: SchemeBalanceDetails
        :return: dict
        """
        # The spec requires currency to be returned as a float this is done at final format since any
        # subsequent arithmetic function would cause a rounding error.
        if is_currency and self.precision is not None:
            value = float(Decimal(value).quantize(self.precision, rounding=ROUND_HALF_UP))
        else:
            value = int(value)

        return {
            "value": value,
            "currency": info.currency,
            "prefix": info.prefix,
            "suffix": info.suffix,
            "description": info.description,
            "updated_at": self.updated_at,
            "reward_tier": self.reward_tier,
        }

    def _get_balances(self):
        self.data = []
        if self.point_balance is not None and self.point_info:
            self.data.append(self._format_balance(self.point_balance, self.point_info, False))

        if self.value_balance is not None and self.value_info:
            self.data.append(self._format_balance(self.value_balance, self.value_info, True))


class Category(models.Model):
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name


def _default_transaction_headers():
    return ["Date", "Reference", "Points"]


class SchemeBundleAssociation(models.Model):
    ACTIVE = 0
    SUSPENDED = 1
    INACTIVE = 2
    STATUSES = (
        (ACTIVE, "Active"),
        (SUSPENDED, "Suspended"),
        (INACTIVE, "Inactive"),
    )
    scheme = models.ForeignKey("Scheme", on_delete=models.CASCADE)
    bundle = models.ForeignKey("user.ClientApplicationBundle", on_delete=models.CASCADE)
    status = models.IntegerField(choices=STATUSES, default=ACTIVE)
    test_scheme = models.BooleanField(default=False)
    plan_popularity = models.IntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(1)],
        help_text="positive number, 1 being the most popular",
    )

    @classmethod
    def get_status_by_bundle_id_and_scheme_id(cls, bundle_id: str, scheme_id: int) -> dict:
        return cls.objects.filter(bundle__bundle_id=bundle_id, scheme_id=scheme_id).values("status")


class SchemeContent(models.Model):
    column = models.CharField(max_length=50)
    value = models.TextField()
    scheme = models.ForeignKey("scheme.Scheme", on_delete=models.CASCADE)

    def __str__(self):
        return self.column


class SchemeFee(models.Model):
    fee_type = models.CharField(max_length=50)
    amount = models.DecimalField(max_digits=6, decimal_places=2)
    scheme = models.ForeignKey("scheme.Scheme", on_delete=models.CASCADE)

    def __str__(self):
        return self.fee_type


class Scheme(models.Model):
    PLL = 1
    STORE = 2
    ENGAGE = 3
    COMING_SOON = 4
    TIERS = ((1, "PLL"), (2, "Store"), (3, "Engage"), (4, "Coming Soon"))
    TRANSACTION_MATCHING_TIERS = [PLL, ENGAGE]

    MAX_POINTS_VALUE_LENGTHS = (
        (0, "0 (no numeric points value)"),
        (1, "1 (0-9)"),
        (2, "2 (0-99)"),
        (3, "3 (0-999)"),
        (4, "4 (0+)"),
    )
    MAX_POINTS_VALUE_LENGTH = 11

    # this is the same slugs found in the active.py file in the midas repo
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    url = models.URLField()
    company = models.CharField(max_length=200)
    company_url = models.URLField(blank=True)
    forgotten_password_url = models.URLField(max_length=500, blank=True)
    join_url = models.URLField(blank=True)
    join_t_and_c = models.TextField(blank=True, verbose_name="Join terms & conditions")
    link_account_text = models.TextField(blank=True)

    tier = models.IntegerField(choices=TIERS)
    transaction_headers = ArrayField(models.CharField(max_length=40), default=_default_transaction_headers)

    ios_scheme = models.CharField(max_length=255, blank=True, verbose_name="iOS scheme")
    itunes_url = models.URLField(blank=True, verbose_name="iTunes URL")
    android_app_id = models.CharField(max_length=255, blank=True, verbose_name="Android app ID")
    play_store_url = models.URLField(blank=True, verbose_name="Play store URL")

    barcode_type = models.IntegerField(choices=BARCODE_TYPES, blank=True, null=True)
    scan_message = models.CharField(max_length=100)
    has_transactions = models.BooleanField(default=False)
    has_points = models.BooleanField(default=False)

    max_points_value_length = models.IntegerField(
        choices=MAX_POINTS_VALUE_LENGTHS,
        default=4,
        help_text="The maximum number of digits the points value will reach. "
        "This cannot be higher than four, because any arbitrarily "
        "large number can be compressed down to four digits.",
    )
    point_name = models.CharField(
        max_length=MAX_POINTS_VALUE_LENGTH - 1,
        default="points",
        blank=True,
        help_text="This field must have a length that, when added to the value of the above "
        f"field, is less than or equal to {MAX_POINTS_VALUE_LENGTH - 1}.",
    )

    identifier = models.CharField(max_length=30, blank=True, help_text="Regex identifier for barcode")
    colour = RGBColorField(blank=True)
    secondary_colour = models.CharField(
        max_length=7, blank=True, default="", help_text='Hex string e.g "#112233"', validators=[validate_hex_colour]
    )
    text_colour = models.CharField(
        max_length=7, blank=True, default="", help_text='Hex string e.g "#112233"', validators=[validate_hex_colour]
    )
    category = models.ForeignKey(Category, on_delete=models.PROTECT)

    card_number_regex = models.CharField(max_length=100, blank=True, help_text="Regex to map barcode to card number")
    barcode_regex = models.CharField(max_length=100, blank=True, help_text="Regex to map card number to barcode")
    card_number_prefix = models.CharField(
        max_length=100, blank=True, help_text="Prefix to from barcode -> card number mapping"
    )
    barcode_prefix = models.CharField(
        max_length=100, blank=True, help_text="Prefix to from card number -> barcode mapping"
    )

    # ubiquity fields
    authorisation_required = models.BooleanField(default=False)
    digital_only = models.BooleanField(default=False)
    plan_name = models.CharField(max_length=50, null=True, blank=True)
    plan_name_card = models.CharField(max_length=50, null=True, blank=True)
    plan_summary = models.TextField(default="", blank=True, max_length=250)
    plan_description = models.TextField(default="", blank=True, max_length=500)
    enrol_incentive = models.CharField(max_length=250, null=False, blank=True)
    barcode_redeem_instructions = models.TextField(default="", blank=True)
    plan_register_info = models.TextField(default="", blank=True)
    linking_support = ArrayField(
        models.CharField(max_length=50),
        default=list,
        blank=True,
        help_text="journeys supported by the scheme in the ubiquity endpoints, " "ie: ADD, REGISTRATION, ENROL",
    )

    formatted_images = JSONField(default=dict, blank=True)
    plan_popularity = models.PositiveSmallIntegerField(null=True, default=None, blank=True)
    balance_renew_period = models.IntegerField(
        default=60 * 20, help_text="Time, in seconds, to allow before calling the merchant to refresh a balance"
    )  # 20 minute default
    go_live = models.DateField(null=True, blank=True)
    vop_merchant_group = models.ForeignKey(
        "payment_card.VopMerchantGroup",
        related_name="schemes",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="If not set, will fallback to the default VopMerchantGroup",
    )

    @cached_property
    def manual_question(self):
        return self.questions.filter(manual_question=True).first()

    @cached_property
    def scan_question(self):
        return self.questions.filter(scan_question=True).first()

    @cached_property
    def one_question_link(self):
        return self.questions.filter(one_question_link=True).first()

    @property
    def join_questions(self):
        return {
            question
            for question in self.questions.all()
            if question.options == (question.options | SchemeCredentialQuestion.JOIN)
        }

    @cached_property
    def link_questions(self):
        return self.questions.filter(options=F("options").bitor(SchemeCredentialQuestion.LINK))

    @cached_property
    def get_required_questions(self):
        return self.questions.filter(
            Q(manual_question=True) | Q(scan_question=True) | Q(one_question_link=True)
        ).values("id", "type")

    @staticmethod
    def get_question_type_dict(question_list: Iterable["SchemeCredentialQuestion"]) -> dict:
        """
        Returns a dict per field type to map scheme credential column names to the question slug and answer type
        e.g:
        {
            "add_fields": {
                "Email": {"type": "email", "answer_type": 0},
                ...
            },
            "auth_fields": {
                "Password": {"type": "password", "answer_type": 1},
                ...
            },
            "enrol_fields": {
                "Password": {"type": "password_2", "answer_type": 1},
                ...
            },
            "registration_fields": {
                ...
            },
        }
        """
        fields_to_field = {
            "add_fields": "add_field",
            "authorise_fields": "auth_field",
            "registration_fields": "register_field",
            "enrol_fields": "enrol_field",
        }

        question_type_dict = {fields: {} for fields in fields_to_field}
        for question in question_list:
            for fields in fields_to_field:
                if getattr(question, fields_to_field[fields]):
                    question_type_dict[fields][question.label] = {
                        "type": question.type,
                        "answer_type": question.answer_type,
                    }

        return question_type_dict

    @classmethod
    def get_scheme_and_questions_by_scheme_id(cls, scheme_id: int) -> "Scheme":
        return cls.objects.prefetch_related("questions").get(pk=scheme_id)

    def __str__(self):
        return f"{self.name} ({self.company})"


class ConsentsManager(models.Manager):
    def get_queryset(self):
        return super(ConsentsManager, self).get_queryset().exclude(is_enabled=False).order_by("journey", "order")


class JourneyTypes(IntEnum):
    JOIN = 0
    LINK = 1
    ADD = 2
    UPDATE = 3
    REGISTER = 4
    UNKNOWN = 5


class Control(models.Model):
    JOIN_KEY = "join_button"
    ADD_KEY = "add_button"

    KEY_CHOICES = ((JOIN_KEY, "Join Button - Add Card screen"), (ADD_KEY, "Add Button - Add Card screen"))

    key = models.CharField(max_length=50, choices=KEY_CHOICES)
    label = models.CharField(max_length=50, blank=True)
    hint_text = models.CharField(max_length=250, blank=True)

    scheme = models.ForeignKey(Scheme, related_name="controls", on_delete=models.CASCADE)


class Consent(models.Model):
    journeys = (
        (JourneyTypes.JOIN.value, "join"),
        (JourneyTypes.LINK.value, "link"),
        (JourneyTypes.ADD.value, "add"),
    )

    check_box = models.BooleanField()
    text = models.TextField()
    scheme = models.ForeignKey(Scheme, related_name="consents", on_delete=models.CASCADE)
    is_enabled = models.BooleanField(default=True)
    required = models.BooleanField()
    order = models.IntegerField()
    journey = models.IntegerField(choices=journeys)
    slug = models.SlugField(
        max_length=50,
        help_text="Slug must match the opt-in field name in the request sent to the merchant e.g marketing_opt_in",
    )
    created_on = models.DateTimeField(auto_now_add=True)
    modified_on = models.DateTimeField(auto_now=True)

    objects = ConsentsManager()
    all_objects = models.Manager()

    @property
    def short_text(self):
        return truncatewords(self.text, 5)

    def __str__(self):
        return f"({self.scheme.slug}) {self.id}: {self.short_text}"

    class Meta:
        unique_together = ("slug", "scheme", "journey")

    @classmethod
    def get_checkboxes_by_scheme_and_journey_type(cls, scheme: Scheme, journey_type: int) -> "QuerySet":
        return cls.objects.filter(scheme=scheme, journey=journey_type, check_box=True).all()


class Exchange(models.Model):
    donor_scheme = models.ForeignKey("scheme.Scheme", related_name="donor_in", on_delete=models.CASCADE)
    host_scheme = models.ForeignKey("scheme.Scheme", related_name="host_in", on_delete=models.CASCADE)

    exchange_rate_donor = models.IntegerField(default=1)
    exchange_rate_host = models.IntegerField(default=1)

    transfer_min = models.DecimalField(default=0.0, decimal_places=2, max_digits=12, null=True, blank=True)
    transfer_max = models.DecimalField(decimal_places=2, max_digits=12, null=True, blank=True)
    transfer_multiple = models.DecimalField(decimal_places=2, max_digits=12, null=True, blank=True)

    tip_in_url = models.URLField()
    info_url = models.URLField()

    flag_auto_tip_in = models.IntegerField(choices=((0, "No"), (1, "Yes")))

    transaction_reference = models.CharField(max_length=24, default="Convert", editable=False)

    start_date = models.DateField(null=True, blank=True, editable=False)
    end_date = models.DateField(null=True, blank=True, editable=False)

    def __str__(self):
        return f"{self.donor_scheme.name} -> {self.host_scheme.name}"


class ActiveSchemeImageManager(models.Manager):
    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(start_date__lt=timezone.now())
            .filter(Q(end_date__isnull=True) | Q(end_date__gte=timezone.now()))
            .exclude(status=Image.DRAFT)
        )


class SchemeImage(Image):
    objects = ActiveSchemeImageManager()
    scheme = models.ForeignKey("scheme.Scheme", related_name="images", on_delete=models.CASCADE)


def _update_scheme_images(instance: SchemeImage) -> None:
    scheme = instance.scheme
    query = {
        "scheme": scheme,
        "status": Image.PUBLISHED,
        "image_type_code__in": [Image.HERO, Image.ICON, Image.ALT_HERO, Image.TIER],
    }
    formatted_images = {}
    tier_images = {}
    # using SchemeImage.all_objects instead of scheme.images to bypass ActiveSchemeImageManager
    for img in SchemeImage.all_objects.filter(**query).all():
        formatted_img = img.ubiquity_format()
        if img.image_type_code == Image.TIER:
            if img.reward_tier not in tier_images:
                tier_images[img.reward_tier] = {}

            tier_images[img.reward_tier][img.id] = formatted_img
        else:
            if img.image_type_code not in formatted_images:
                formatted_images[img.image_type_code] = {}

            formatted_images[img.image_type_code][img.id] = formatted_img

    scheme.formatted_images = {"images": formatted_images, "tier_images": tier_images}
    scheme.save(update_fields=["formatted_images"])


@receiver(signals.post_save, sender=SchemeImage)
def update_scheme_images_on_save(sender, instance, created, **kwargs):
    _update_scheme_images(instance)


@receiver(signals.post_delete, sender=SchemeImage)
def update_scheme_images_on_delete(sender, instance, **kwargs):
    _update_scheme_images(instance)


class SchemeAccountImage(Image):
    objects = ActiveSchemeImageManager()
    scheme = models.ForeignKey("scheme.Scheme", null=True, blank=True, on_delete=models.SET_NULL)
    scheme_accounts = models.ManyToManyField("scheme.SchemeAccount", related_name="scheme_accounts_set")

    def __str__(self):
        return self.description


@receiver(signals.m2m_changed, sender=SchemeAccountImage.scheme_accounts.through)
def update_scheme_account_images_on_save(sender, instance, action, **kwargs):
    wrong_image_type = instance.image_type_code not in [Image.HERO, Image.ICON, Image.ALT_HERO, Image.TIER]
    wrong_action = action != "post_add"
    image_is_draft = instance.status == Image.DRAFT

    if wrong_action or image_is_draft or wrong_image_type:
        return

    formatted_image = instance.ubiquity_format()
    for scheme_account in instance.scheme_accounts.all():
        if instance.image_type_code == Image.TIER:
            account_tier_images = scheme_account.formatted_images.get("tier_images", {})
            if instance.reward_tier not in account_tier_images:
                account_tier_images[instance.reward_tier] = {}

            account_tier_images[instance.reward_tier][instance.id] = formatted_image
            scheme_account.formatted_images.update({"tier_images": account_tier_images})
        else:
            account_images = scheme_account.formatted_images.get("images", {})
            if instance.image_type_code not in account_images:
                account_images[instance.image_type_code] = {}

            account_images[instance.image_type_code][instance.id] = formatted_image
            scheme_account.formatted_images.update({"images": account_images})

        scheme_account.save(update_fields=["formatted_images"])


@receiver(signals.pre_delete, sender=SchemeAccountImage)
def update_scheme_account_images_on_delete(sender, instance, **kwargs):
    if instance.image_type_code not in [Image.HERO, Image.ICON, Image.ALT_HERO, Image.TIER]:
        return

    for scheme_account in instance.scheme_accounts.all():
        try:
            if instance.image_type_code == Image.TIER:
                del scheme_account.formatted_images["tier_images"][str(instance.reward_tier)][str(instance.id)]
            else:
                del scheme_account.formatted_images["images"][str(instance.image_type_code)][str(instance.id)]
        except (KeyError, ValueError):
            pass
        else:
            scheme_account.save(update_fields=["formatted_images"])


class ActiveSchemeIgnoreQuestionManager(BulkUpdateManager):
    use_in_migrations = True

    def get_queryset(self):
        return super(ActiveSchemeIgnoreQuestionManager, self).get_queryset().filter(is_deleted=False)


class SchemeAccount(models.Model):
    # Journey types
    JOURNEYS = (
        (JourneyTypes.UNKNOWN, "Unknown"),
        (JourneyTypes.JOIN, "Enrol"),
        (JourneyTypes.ADD, "Add"),
        (JourneyTypes.REGISTER, "Register"),
    )

    user_set = models.ManyToManyField(
        "user.CustomUser", through="ubiquity.SchemeAccountEntry", related_name="scheme_account_set"
    )
    scheme = models.ForeignKey("scheme.Scheme", on_delete=models.PROTECT)
    order = models.IntegerField()
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    link_date = models.DateTimeField(null=True, blank=True)
    join_date = models.DateTimeField(null=True, blank=True)
    all_objects = models.Manager()
    objects = ActiveSchemeIgnoreQuestionManager()

    balances = JSONField(default=dict, null=True, blank=True)
    vouchers = JSONField(default=dict, null=True, blank=True)
    transactions = JSONField(default=list, null=True, blank=True)

    card_number = models.CharField(max_length=250, blank=True, db_index=True, default="")
    barcode = models.CharField(max_length=250, blank=True, db_index=True, default="")
    alt_main_answer = models.CharField(max_length=250, blank=True, db_index=True, default="")
    merchant_identifier = models.CharField(max_length=250, blank=True, db_index=True, default="")

    pll_links = JSONField(default=list, null=True, blank=True)
    formatted_images = JSONField(default=dict, null=True, blank=True)
    originating_journey = models.IntegerField(choices=JOURNEYS, default=JourneyTypes.UNKNOWN)

    def collect_pending_consents(self):
        user_consents = self.userconsent_set.filter(status=ConsentStatus.PENDING).values()
        return self.format_user_consents(user_consents)

    @staticmethod
    def format_user_consents(user_consents):
        return [
            {
                "id": user_consent["id"],
                "slug": user_consent["slug"],
                "value": user_consent["value"],
                "created_on": arrow.get(user_consent["created_on"]).for_json(),
                "journey_type": user_consent["metadata"]["journey"],
            }
            for user_consent in user_consents
        ]

    @staticmethod
    def _process_midas_response(
        response, scheme_account_entry: "SchemeAccountEntry"
    ) -> tuple[dict | None, AccountLinkStatus, tuple[bool, AccountLinkStatus] | None]:
        # todo: liaise with Merchant to work out how we parse credentials back in.
        points = None
        previous_status = scheme_account_entry.link_status
        dw_event = None

        if response.status_code == 200:
            points = response.json()
            account_status = AccountLinkStatus.PENDING if points.get("pending") else AccountLinkStatus.ACTIVE
            points["balance"] = points.get("balance")  # serializers.DecimalField does not allow blank fields
            points["is_stale"] = False

        elif response.status_code >= 500 and previous_status == AccountLinkStatus.ACTIVE:
            # When receiving a 500 error from Midas, keep SchemeAccount active only
            # if it's already active.
            account_status = previous_status
            logger.info(f"Ignoring Midas {response.status_code} response code")

        elif response.status_code not in [status[0] for status in AccountLinkStatus.extended_statuses()]:
            account_status = AccountLinkStatus.UNKNOWN_ERROR

        else:
            account_status = response.status_code

        # data warehouse event, not used for subsequent midas calls
        # only when a scheme_account was in a pre-pending status
        if previous_status in AccountLinkStatus.pre_pending_statuses():
            # dw_event is a tuple(success: bool, SchemeAccount.STATUS: int)
            dw_event = (account_status == AccountLinkStatus.ACTIVE, previous_status)

        return points, account_status, dw_event

    def get_key_cred_value_from_question_type(self, question_type):
        if question_type == CARD_NUMBER:
            return self.card_number
        if question_type == BARCODE:
            return self.barcode
        else:
            return self.alt_main_answer

    @staticmethod
    def get_key_cred_field_from_question_type(question_type):
        if question_type == CARD_NUMBER:
            return "card_number"
        if question_type == BARCODE:
            return "barcode"
        else:
            return "alt_main_answer"

    def _get_midas_balance(
        self,
        journey,
        scheme_account_entry: SchemeAccountEntry,
        credentials_override: dict | None = None,
        headers: dict | None = None,
    ) -> tuple[dict | None, AccountLinkStatus, tuple[bool, AccountLinkStatus] | None]:
        points = None
        account_status = scheme_account_entry.link_status
        dw_event = None

        if scheme_account_entry.link_status in AccountLinkStatus.join_exclude_balance_statuses() or not (
            credentials := scheme_account_entry.credentials(credentials_override)
        ):
            return points, account_status, dw_event

        try:
            response = self._get_balance_request(
                credentials, journey, scheme_account_entry, headers.get("X-azure-ref", None) if headers else None
            )
            points, account_status, dw_event = self._process_midas_response(response, scheme_account_entry)
            self._received_balance_checks(scheme_account_entry)
        except requests.exceptions.ConnectionError:
            account_status = AccountLinkStatus.MIDAS_UNREACHABLE

        return points, account_status, dw_event

    def _received_balance_checks(self, scheme_account_entry):
        saved = False
        if scheme_account_entry.link_status in AccountLinkStatus.join_action_required():
            queryset = scheme_account_entry.schemeaccountcredentialanswer_set
            card_number = self.card_number
            if card_number:
                queryset = queryset.exclude(answer=card_number)

            queryset.all().delete()

        return saved

    def _get_balance_request(self, credentials, journey, scheme_account_entry, x_azure_ref: str | None = None):
        # todo: liaise with Midas to work out what we need to see here
        user_set = ",".join([str(u.id) for u in self.user_set.all()])
        parameters = {
            "scheme_account_id": self.id,
            "credentials": credentials,
            "user_set": user_set,
            "status": scheme_account_entry.link_status,
            "journey_type": journey.value,
            "bink_user_id": scheme_account_entry.user.id,
        }
        midas_balance_uri = f"{settings.MIDAS_URL}/{self.scheme.slug}/balance"
        headers = {
            "transaction": str(uuid.uuid1()),
            "User-agent": f"Hermes on {socket.gethostname()}",
            "X-azure-ref": x_azure_ref,
        }
        response = requests.get(midas_balance_uri, params=parameters, headers=headers)
        return response

    def get_journey_type(self, is_scheme_account_entry_authorised: bool):
        if is_scheme_account_entry_authorised:
            return JourneyTypes.UPDATE
        else:
            return JourneyTypes.LINK

    def check_balance_and_vouchers(self, balance=None, voucher_resp=None):
        update_fields = []

        if balance and balance != self.balances:
            self.balances = balance
            update_fields.append("balances")

        if voucher_resp and voucher_resp != self.vouchers:
            self.vouchers = voucher_resp
            update_fields.append("vouchers")

        return update_fields

    def get_balance(
        self,
        scheme_account_entry: SchemeAccountEntry,
        credentials_override: dict | None = None,
        journey: JourneyTypes = None,
        headers: dict | None = None,
    ) -> tuple[list[dict], tuple[bool, AccountLinkStatus] | None]:
        old_status = scheme_account_entry.link_status
        journey = journey or self.get_journey_type(scheme_account_entry.authorised)

        balance, account_status, dw_event = self._get_midas_balance(
            journey=journey,
            credentials_override=credentials_override,
            scheme_account_entry=scheme_account_entry,
            headers=headers,
        )

        voucher_resp = None
        if balance:
            if "vouchers" in balance:
                voucher_resp = self.make_vouchers_response(balance["vouchers"])
                del balance["vouchers"]

            balance.update({"updated_at": arrow.utcnow().int_timestamp, "scheme_id": self.scheme_id})
            balance: list[dict] = UbiquityBalanceHandler(balance).data

        update_fields = self.check_balance_and_vouchers(balance=balance, voucher_resp=voucher_resp)

        if account_status != old_status:
            scheme_account_entry.set_link_status(account_status)
            capture_membership_card_status_change_metric(
                scheme_slug=self.scheme.slug,
                old_status=old_status,
                new_status=scheme_account_entry.link_status,
            )
            logger.info(
                "%s of id %s has been updated with status: %s",
                self.__class__.__name__,
                self.id,
                scheme_account_entry.link_status,
            )

        if update_fields:
            self.save(update_fields=update_fields)

        return balance, dw_event

    def make_vouchers_response(self, vouchers: list) -> list:
        """
        Vouchers come from Midas with the following fields:
        * issue_date: int, optional
        * redeem_date: int, optional
        * expiry_date: int, optional
        * code: str, optional
        * type: int, required
        * value: float, optional
        * target_value: float, optional
        """

        voucher_scheme_slugs = {
            voucher_fields.get("voucher_scheme_slug")
            for voucher_fields in vouchers
            if voucher_fields.get("voucher_scheme_slug")
        }

        voucher_schemes = VoucherScheme.objects.filter(
            Q(slug__in=voucher_scheme_slugs) | Q(default=True), scheme=self.scheme
        )
        voucher_scheme_mapping = {scheme.slug or "default": scheme for scheme in voucher_schemes}

        vouchers_response = []
        for voucher_fields in vouchers:
            voucher_scheme_key = voucher_fields.get("voucher_scheme_slug", "default")
            try:
                voucher_scheme = voucher_scheme_mapping[voucher_scheme_key]
            except KeyError:
                if voucher_scheme_key == "default":
                    msg: tuple = (
                        "Default VoucherScheme not found. Please set a default VoucherScheme for scheme '%s'.",
                        self.scheme.slug,
                    )
                else:
                    msg: tuple = (
                        "VoucherScheme not found. Please check the voucher configuration for scheme '%s' - "
                        "VoucherScheme slug: %s",
                        self.scheme.slug,
                        voucher_scheme_key,
                    )

                logger.error(*msg)
                continue

            vouchers_response.append(self.make_single_voucher(voucher_fields, voucher_scheme))

        return vouchers_response

    @staticmethod
    def make_single_voucher(voucher_fields: dict, voucher_scheme: "VoucherScheme") -> dict:
        earn_target_value: float = voucher_scheme.get_earn_target_value(voucher_fields=voucher_fields)
        earn_value: float | int = voucher_scheme.get_earn_value(
            voucher_fields=voucher_fields, earn_target_value=earn_target_value
        )

        issue_date = arrow.get(voucher_fields["issue_date"]) if "issue_date" in voucher_fields else None
        redeem_date = arrow.get(voucher_fields["redeem_date"]) if "redeem_date" in voucher_fields else None

        expiry_date = vouchers.get_expiry_date(voucher_fields)
        conversion_date = arrow.get(voucher_fields["conversion_date"]) if "conversion_date" in voucher_fields else None

        headline_template = voucher_scheme.get_headline(voucher_fields["state"])
        headline = vouchers.apply_template(
            headline_template,
            voucher_scheme=voucher_scheme,
            earn_value=earn_value,
            earn_target_value=earn_target_value,
        )

        body_text = voucher_scheme.get_body_text(voucher_fields["state"])

        voucher = {
            "state": voucher_fields["state"],
            "earn": {
                "type": voucher_scheme.earn_type,
                "prefix": voucher_scheme.earn_prefix,
                "suffix": voucher_scheme.earn_suffix,
                "currency": voucher_scheme.earn_currency,
                "value": earn_value,
                "target_value": earn_target_value,
            },
            "burn": {
                "currency": voucher_scheme.burn_currency,
                "prefix": voucher_scheme.burn_prefix,
                "suffix": voucher_scheme.burn_suffix,
                "type": voucher_scheme.burn_type,
                "value": voucher_scheme.burn_value,
            },
            "barcode_type": voucher_scheme.barcode_type,
            "headline": headline,
            "body_text": body_text,
            "subtext": voucher_scheme.subtext,
            "terms_and_conditions_url": voucher_scheme.terms_and_conditions_url,
        }

        if issue_date is not None:
            voucher.update(
                {
                    "date_issued": issue_date.int_timestamp,
                    "expiry_date": expiry_date.int_timestamp if expiry_date else None,
                }
            )

        if redeem_date is not None:
            voucher["date_redeemed"] = redeem_date.int_timestamp

        if "code" in voucher_fields:
            voucher["code"] = voucher_fields["code"]

        if conversion_date is not None:
            voucher["conversion_date"] = conversion_date.int_timestamp

        return voucher

    def set_register_originating_journey(self, *, commit_change=True) -> None:
        self.originating_journey = JourneyTypes.REGISTER
        if commit_change:
            self.save(update_fields=["originating_journey"])

    def set_add_originating_journey(self, *, commit_change=True) -> None:
        if self.originating_journey == JourneyTypes.UNKNOWN:
            self.originating_journey = JourneyTypes.ADD
            if commit_change:
                self.save(update_fields=["originating_journey"])

    def delete_cached_balance(self):
        cache_key = f"scheme_{self.pk}"
        cache.delete(cache_key)

    def delete_saved_balance(self):
        self.balances: dict = {}
        self.save(update_fields=["balances"])

    def question(self, question_type):
        """
        Return the scheme question instance for the given question type
        :param question_type:
        :return:
        """
        return SchemeCredentialQuestion.objects.filter(type=question_type, scheme=self.scheme).first()

    @property
    def card_label(self):
        if self.alt_main_answer:
            return self.alt_main_answer

        if not self.barcode:
            return None

        if self.scheme.card_number_regex:
            try:
                regex_match = re.search(self.scheme.card_number_regex, self.barcode)
            except sre_constants.error:
                return None
            if regex_match:
                try:
                    return self.scheme.card_number_prefix + regex_match.group(1)
                except IndexError:
                    return None
        return self.barcode

    def get_transaction_matching_user_id(self):
        # todo: Awaiting confirmation of whether this should be sent as a list or is even needed by harmonia.
        try:
            return (
                self.user_set.filter(schemeaccountentry__link_status=AccountLinkStatus.ACTIVE)
                .order_by("date_joined")
                .values("id")
                .first()
                .get("id")
            )
        except AttributeError:
            return None

    def save(self, *args, **kwargs):
        # Only when we update, we update the updated date time.
        if kwargs.get("update_fields"):
            kwargs["update_fields"].append("updated")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.scheme.name} - id: {self.id}"

    class Meta:
        ordering = ["order", "-created"]


class SchemeOverrideError(models.Model):
    ERROR_CODE_CHOICES = tuple((status[0], status[2]) for status in AccountLinkStatus.extended_statuses())
    ERROR_SLUG_CHOICES = tuple((status[2], status[2]) for status in AccountLinkStatus.extended_statuses())
    REASON_CODE_CHOICES = tuple((reason_code[0], reason_code[0]) for reason_code in REASON_CODES)
    scheme = models.ForeignKey("scheme.Scheme", on_delete=models.CASCADE)
    error_code = models.IntegerField(choices=ERROR_CODE_CHOICES)
    reason_code = models.CharField(max_length=50, choices=REASON_CODE_CHOICES)
    error_slug = models.CharField(max_length=50, choices=ERROR_SLUG_CHOICES)
    message = models.TextField()
    channel = models.ForeignKey("user.ClientApplicationBundle", on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f"({self.reason_code}) {self.scheme.name}: {self.message}"

    class Meta:
        unique_together = ("error_code", "scheme", "channel")


class SchemeCredentialQuestion(models.Model):
    NONE = 0
    LINK = 1 << 0
    JOIN = 1 << 1
    OPTIONAL_JOIN = 1 << 2 | JOIN
    LINK_AND_JOIN = LINK | JOIN
    MERCHANT_IDENTIFIER = 1 << 3

    OPTIONS = (
        (NONE, "None"),
        (LINK, "Link"),
        (JOIN, "Join"),
        (OPTIONAL_JOIN, "Join (optional)"),
        (LINK_AND_JOIN, "Link & Join"),
        (MERCHANT_IDENTIFIER, "Merchant Identifier"),
    )

    # ubiquity choices
    ANSWER_TYPE_CHOICES = (
        (0, "text"),
        (1, "sensitive"),
        (2, "choice"),
        (3, "boolean"),
        (4, "payment_card_hash"),
        (5, "date"),
    )

    scheme = models.ForeignKey("Scheme", related_name="questions", on_delete=models.PROTECT)
    order = models.IntegerField(default=0)
    type = models.CharField(max_length=250, choices=CREDENTIAL_TYPES)
    label = models.CharField(max_length=250)
    third_party_identifier = models.BooleanField(default=False)
    manual_question = models.BooleanField(default=False)
    scan_question = models.BooleanField(default=False)
    one_question_link = models.BooleanField(default=False)
    options = models.IntegerField(choices=OPTIONS, default=NONE)

    # ubiquity fields
    validation = models.TextField(default="", blank=True, max_length=250)
    validation_description = models.TextField(default="", blank=True, max_length=250)
    description = models.CharField(default="", blank=True, max_length=250)
    # common_name = models.CharField(default='', blank=True, max_length=50)
    answer_type = models.IntegerField(default=0, choices=ANSWER_TYPE_CHOICES)
    choice = ArrayField(models.CharField(max_length=50), null=True, blank=True)
    add_field = models.BooleanField(default=False)
    auth_field = models.BooleanField(default=False)
    register_field = models.BooleanField(default=False)
    enrol_field = models.BooleanField(default=False)
    is_optional = models.BooleanField(
        default=False, help_text="Whether this field is optional for Enrol & Register credentials"
    )
    is_stored = models.BooleanField(
        default=True, help_text="Whether the answer is stored long-term or disposed of after the initial request"
    )

    def clean(self):
        if self.is_optional and (
            not (self.enrol_field or self.register_field) or any([self.add_field, self.auth_field])
        ):
            raise ValidationError({"is_optional": _("This field can only be used for enrol & register credentials.")})

    @property
    def required(self):
        return self.options is not self.OPTIONAL_JOIN

    @property
    def question_choices(self):
        try:
            choices = SchemeCredentialQuestionChoice.objects.get(scheme=self.scheme, scheme_question=self.type)
            return choices.values
        except SchemeCredentialQuestionChoice.DoesNotExist:
            return []

    class Meta:
        ordering = ["order"]
        unique_together = ("scheme", "type")

    def __str__(self):
        return self.type


class SchemeCredentialQuestionChoice(models.Model):
    scheme = models.ForeignKey("Scheme", on_delete=models.CASCADE)
    scheme_question = models.CharField(max_length=250, choices=CREDENTIAL_TYPES)

    @property
    def values(self):
        choice_values = self.choice_values.all()
        return [str(value) for value in choice_values]

    class Meta:
        unique_together = ("scheme", "scheme_question")


class SchemeCredentialQuestionChoiceValue(models.Model):
    choice = models.ForeignKey("SchemeCredentialQuestionChoice", related_name="choice_values", on_delete=models.CASCADE)
    value = models.CharField(max_length=250)
    order = models.IntegerField(default=0)

    def __str__(self):
        return self.value

    class Meta:
        ordering = ["order", "value"]


class SchemeDetail(models.Model):
    TYPE_CHOICES = ((0, "Tier"),)

    scheme_id = models.ForeignKey("Scheme", on_delete=models.CASCADE)
    type = models.IntegerField(choices=TYPE_CHOICES, default=0)
    name = models.CharField(max_length=255)
    description = models.TextField()


class SchemeBalanceDetails(models.Model):
    scheme_id = models.ForeignKey("Scheme", on_delete=models.CASCADE)
    currency = models.CharField(default="", blank=True, max_length=50)
    prefix = models.CharField(default="", blank=True, max_length=50)
    suffix = models.CharField(default="", blank=True, max_length=50)
    description = models.TextField(default="", blank=True, max_length=250)

    class Meta:
        verbose_name_plural = "balance details"


class SchemeAccountCredentialAnswer(models.Model):
    scheme_account_entry = models.ForeignKey(SchemeAccountEntry, on_delete=models.CASCADE, null=True)
    question = models.ForeignKey(SchemeCredentialQuestion, null=True, on_delete=models.PROTECT)
    answer = models.CharField(max_length=250)

    def clean_answer(self):
        if self.question.type in ENCRYPTED_CREDENTIALS:
            return "****"
        return self.answer

    @staticmethod
    def save_answer(question: SchemeCredentialQuestion, answer: str, scheme_account_entry: SchemeAccountEntry) -> None:
        if question.is_stored:
            SchemeAccountCredentialAnswer.objects.update_or_create(
                question=question,
                defaults={"answer": answer},
                scheme_account_entry=scheme_account_entry,
            )

    def __str__(self):
        return self.clean_answer()

    class Meta:
        unique_together = ("scheme_account_entry", "question")


@receiver(signals.pre_save, sender=SchemeAccountCredentialAnswer)
def encryption_handler(sender, instance, **kwargs):
    if instance.question.type in ENCRYPTED_CREDENTIALS:
        try:
            encrypted_answer = AESCipher(AESKeyNames.LOCAL_AES_KEY).encrypt(instance.answer).decode("utf-8")
        except AttributeError:
            answer = str(instance.answer)
            encrypted_answer = AESCipher(AESKeyNames.LOCAL_AES_KEY).encrypt(answer).decode("utf-8")

        instance.answer = encrypted_answer


class ConsentStatus(IntEnum):
    PENDING = 0
    SUCCESS = 1
    FAILED = 2
    NOT_SENT = 3


class UserConsent(models.Model):
    created_on = models.DateTimeField(default=timezone.now)
    user = models.ForeignKey("user.CustomUser", null=True, on_delete=models.SET_NULL)
    scheme = models.ForeignKey(Scheme, null=True, on_delete=models.SET_NULL)
    scheme_account = models.ForeignKey(SchemeAccount, null=True, on_delete=models.SET_NULL)
    metadata = JSONField()
    slug = models.SlugField(max_length=50)
    value = models.BooleanField()
    status = models.IntegerField(
        choices=[(status.value, status.name) for status in ConsentStatus], default=ConsentStatus.PENDING
    )

    @property
    def short_text(self):
        metadata = dict(self.metadata)
        return truncatewords(metadata.get("text"), 5)

    def __str__(self):
        return f"{self.user} - {self.slug}: {self.value}"


class ThirdPartyConsentLink(models.Model):
    consent_label = models.CharField(max_length=50)
    client_app = models.ForeignKey("user.ClientApplication", related_name="client_app", on_delete=models.CASCADE)
    scheme = models.ForeignKey("scheme.Scheme", related_name="scheme", on_delete=models.CASCADE)
    consent = models.ForeignKey(Consent, related_name="consent", on_delete=models.CASCADE)

    add_field = models.BooleanField(default=False)
    auth_field = models.BooleanField(default=False)
    register_field = models.BooleanField(default=False)
    enrol_field = models.BooleanField(default=False)

    @classmethod
    def get_by_scheme_and_client(cls, scheme: Scheme, client_app: "ClientApplication") -> "QuerySet":
        return cls.objects.filter(scheme=scheme, client_app=client_app).all()


class VoucherScheme(models.Model):
    EARNTYPE_JOIN = "join"
    EARNTYPE_ACCUMULATOR = "accumulator"
    EARNTYPE_STAMPS = "stamps"

    EARN_TYPES = (
        (EARNTYPE_JOIN, "Join"),
        (EARNTYPE_ACCUMULATOR, "Accumulator"),
        (EARNTYPE_STAMPS, "Stamps"),
    )

    BURNTYPE_VOUCHER = "voucher"
    BURNTYPE_COUPON = "coupon"
    BURNTYPE_DISCOUNT = "discount"

    BURN_TYPES = (
        (BURNTYPE_VOUCHER, "Voucher"),
        (BURNTYPE_COUPON, "Coupon"),
        (BURNTYPE_DISCOUNT, "Discount"),
    )

    VOUCHER_BARCODE_TYPES = (
        *BARCODE_TYPES,
        (9, "Barcode Not Supported"),
    )

    scheme = models.ForeignKey("scheme.Scheme", on_delete=models.CASCADE)

    default = models.BooleanField(
        default=True, help_text="Default voucher scheme when multiple are available for a scheme"
    )
    slug = models.SlugField(null=True, blank=True)

    earn_currency = models.CharField(max_length=50, blank=True, verbose_name="Currency")
    earn_prefix = models.CharField(max_length=50, blank=True, verbose_name="Prefix")
    earn_suffix = models.CharField(max_length=50, blank=True, verbose_name="Suffix")
    earn_type = models.CharField(max_length=50, choices=EARN_TYPES, verbose_name="Earn Type")
    earn_target_value_help_text = (
        "Enter a value in this field if the merchant scheme does not return an earn.target_value for the voucher"
    )
    earn_target_value = models.FloatField(
        blank=True, null=True, verbose_name="Earn Target Value", help_text=earn_target_value_help_text
    )

    burn_currency = models.CharField(max_length=50, blank=True, verbose_name="Currency")
    burn_prefix = models.CharField(max_length=50, blank=True, verbose_name="Prefix")
    burn_suffix = models.CharField(max_length=50, blank=True, verbose_name="Suffix")
    burn_type = models.CharField(max_length=50, choices=BURN_TYPES, verbose_name="Burn Type")
    burn_value = models.FloatField(blank=True, null=True, verbose_name="Value")

    barcode_type = models.IntegerField(choices=VOUCHER_BARCODE_TYPES)

    headline_inprogress = models.CharField(max_length=250, verbose_name="In Progress")
    headline_expired = models.CharField(max_length=250, verbose_name="Expired")
    headline_redeemed = models.CharField(max_length=250, verbose_name="Redeemed")
    headline_issued = models.CharField(max_length=250, verbose_name="Issued")
    headline_cancelled = models.CharField(max_length=250, verbose_name="Cancelled", default="")
    headline_pending = models.CharField(max_length=250, verbose_name="Pending", default="")

    body_text_inprogress = models.TextField(null=False, blank=True, verbose_name="In Progress")
    body_text_expired = models.TextField(null=False, blank=True, verbose_name="Expired")
    body_text_redeemed = models.TextField(null=False, blank=True, verbose_name="Redeemed")
    body_text_issued = models.TextField(null=False, blank=True, verbose_name="Issued")
    body_text_cancelled = models.TextField(null=False, blank=True, verbose_name="Cancelled", default="")
    body_text_pending = models.TextField(null=False, blank=True, verbose_name="Pending", default="")
    subtext = models.CharField(max_length=250, null=False, blank=True)
    terms_and_conditions_url = models.URLField(null=False, blank=True)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["scheme", "slug"],
                name="unique_slug_per_scheme",
                violation_error_message="Each slug must be unique per Scheme",
            ),
            UniqueConstraint(
                fields=["scheme"],
                condition=Q(default=True),
                name="unique_default_per_scheme",
                violation_error_message="There can only be one default VoucherScheme per Scheme",
            ),
        ]

    def __str__(self):
        type_name = dict(self.EARN_TYPES)[self.earn_type]
        return f"{self.scheme.name} {type_name} - id: {self.id}"

    def get_headline(self, state: VoucherStateStr):
        return {
            VoucherStateStr.ISSUED: self.headline_issued,
            VoucherStateStr.IN_PROGRESS: self.headline_inprogress,
            VoucherStateStr.EXPIRED: self.headline_expired,
            VoucherStateStr.REDEEMED: self.headline_redeemed,
            VoucherStateStr.CANCELLED: self.headline_cancelled,
            VoucherStateStr.PENDING: self.headline_pending,
        }[state]

    def get_body_text(self, state: VoucherStateStr):
        return {
            VoucherStateStr.ISSUED: self.body_text_issued,
            VoucherStateStr.IN_PROGRESS: self.body_text_inprogress,
            VoucherStateStr.EXPIRED: self.body_text_expired,
            VoucherStateStr.REDEEMED: self.body_text_redeemed,
            VoucherStateStr.CANCELLED: self.body_text_cancelled,
            VoucherStateStr.PENDING: self.body_text_pending,
        }[state]

    def get_earn_target_value(self, voucher_fields: dict) -> float:
        """
        Get the target value from the incoming voucher, or voucher scheme if it's been set.
        Raise value exception if no value found from either.
        Can be set to zero for compatibility with existing voucher code.

        :param voucher_fields: Incoming voucher dict
        :return: earn target value
        """
        earn_target_value = voucher_fields.get("target_value")

        if earn_target_value is None:
            earn_target_value = self.earn_target_value
            if earn_target_value is None:
                raise ValueError("Earn target value must be set in voucher or voucher scheme config (cannot be None)")

        return float(earn_target_value)

    @staticmethod
    def get_earn_value(voucher_fields: dict, earn_target_value: float) -> float:
        """
        Get the value from the incoming voucher. If it's None then assume
        it's been completed and set to the earn target value, otherwise return the value of the field.
        This can't necessarily be done in Midas, as Midas may not know what the earn target value is
        if the third-party API doesn't supply it.

        :param voucher_fields: Incoming voucher dict
        :param earn_target_value: The target number of stamps to complete
        :return: earn value
        """
        earn_value = voucher_fields.get("value")
        if earn_value is None:
            earn_value = earn_target_value

        return earn_value
