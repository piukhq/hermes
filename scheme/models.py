import json
import re
import socket
import sre_constants
import uuid
from decimal import Decimal
from enum import IntEnum

import arrow
import requests
from analytics.api import update_scheme_account_attribute_new_status, update_scheme_account_attribute
from bulk_update.manager import BulkUpdateManager
from colorful.fields import RGBColorField
from common.models import Image
from django.conf import settings
from django.contrib.postgres.fields import ArrayField, JSONField
from django.core.cache import cache
from django.db import models
from django.db.models import F, Q
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.template.defaultfilters import truncatewords
from django.utils import timezone
from scheme import vouchers
from scheme.credentials import BARCODE, CARD_NUMBER, CREDENTIAL_TYPES, ENCRYPTED_CREDENTIALS
from scheme.encyption import AESCipher
from ubiquity.models import PaymentCardSchemeEntry


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
        (ACTIVE, 'Active'),
        (SUSPENDED, 'Suspended'),
        (INACTIVE, 'Inactive'),
    )
    scheme = models.ForeignKey('Scheme', on_delete=models.CASCADE)
    bundle = models.ForeignKey('user.ClientApplicationBundle', on_delete=models.CASCADE)
    status = models.IntegerField(choices=STATUSES, default=ACTIVE)


BARCODE_TYPES = (
    (0, 'CODE128 (B or C)'),
    (1, 'QrCode'),
    (2, 'AztecCode'),
    (3, 'Pdf417'),
    (4, 'EAN (13)'),
    (5, 'DataMatrix'),
    (6, "ITF (Interleaved 2 of 5)"),
    (7, 'Code 39'),
)


class SchemeContent(models.Model):
    column = models.CharField(max_length=50)
    value = models.TextField()
    scheme = models.ForeignKey('scheme.Scheme', on_delete=models.CASCADE)

    def __str__(self):
        return self.column


class SchemeFee(models.Model):
    fee_type = models.CharField(max_length=50)
    amount = models.DecimalField(max_digits=6, decimal_places=2)
    scheme = models.ForeignKey('scheme.Scheme', on_delete=models.CASCADE)

    def __str__(self):
        return self.fee_type


class Scheme(models.Model):
    PLL = 1
    BASIC = 2
    PARTNER = 3
    TIERS = (
        (1, 'PLL'),
        (2, 'Basic'),
        (3, 'Partner'),
    )
    TRANSACTION_MATCHING_TIERS = [PLL, PARTNER]

    MAX_POINTS_VALUE_LENGTHS = (
        (0, '0 (no numeric points value)'),
        (1, '1 (0-9)'),
        (2, '2 (0-99)'),
        (3, '3 (0-999)'),
        (4, '4 (0+)'),
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

    ios_scheme = models.CharField(max_length=255, blank=True, verbose_name='iOS scheme')
    itunes_url = models.URLField(blank=True, verbose_name='iTunes URL')
    android_app_id = models.CharField(max_length=255, blank=True, verbose_name='Android app ID')
    play_store_url = models.URLField(blank=True, verbose_name='Play store URL')

    barcode_type = models.IntegerField(choices=BARCODE_TYPES, blank=True, null=True)
    scan_message = models.CharField(max_length=100)
    has_transactions = models.BooleanField(default=False)
    has_points = models.BooleanField(default=False)

    max_points_value_length = models.IntegerField(choices=MAX_POINTS_VALUE_LENGTHS, default=4,
                                                  help_text='The maximum number of digits the points value will reach. '
                                                            'This cannot be higher than four, because any arbitrarily '
                                                            'large number can be compressed down to four digits.')
    point_name = models.CharField(max_length=MAX_POINTS_VALUE_LENGTH - 1, default='points', blank=True,
                                  help_text='This field must have a length that, when added to the value of the above '
                                            'field, is less than or equal to {}.'.format(MAX_POINTS_VALUE_LENGTH - 1))

    identifier = models.CharField(max_length=30, blank=True, help_text="Regex identifier for barcode")
    colour = RGBColorField(blank=True)
    test_scheme = models.BooleanField(default=False)
    category = models.ForeignKey(Category, on_delete=models.PROTECT)

    card_number_regex = models.CharField(max_length=100, blank=True,
                                         help_text="Regex to map barcode to card number")
    barcode_regex = models.CharField(max_length=100, blank=True,
                                     help_text="Regex to map card number to barcode")
    card_number_prefix = models.CharField(max_length=100, blank=True,
                                          help_text="Prefix to from barcode -> card number mapping")
    barcode_prefix = models.CharField(max_length=100, blank=True,
                                      help_text="Prefix to from card number -> barcode mapping")

    # ubiquity fields
    authorisation_required = models.BooleanField(default=False)
    digital_only = models.BooleanField(default=False)
    plan_name = models.CharField(max_length=50, null=True, blank=True)
    plan_name_card = models.CharField(max_length=50, null=True, blank=True)
    plan_summary = models.TextField(default='', blank=True, max_length=250)
    plan_description = models.TextField(default='', blank=True, max_length=500)
    enrol_incentive = models.CharField(max_length=250, null=False, blank=True)
    barcode_redeem_instructions = models.TextField(default='', blank=True)
    plan_register_info = models.TextField(default='', blank=True)
    linking_support = ArrayField(models.CharField(max_length=50), default=list, blank=True,
                                 help_text='journeys supported by the scheme in the ubiquity endpoints, '
                                           'ie: ADD, REGISTRATION, ENROL')

    @property
    def manual_question(self):
        return self.questions.filter(manual_question=True).first()

    @property
    def scan_question(self):
        return self.questions.filter(scan_question=True).first()

    @property
    def one_question_link(self):
        return self.questions.filter(one_question_link=True).first()

    @property
    def join_questions(self):
        return self.questions.filter(options=F('options').bitor(SchemeCredentialQuestion.JOIN))

    @property
    def link_questions(self):
        return self.questions.filter(options=F('options').bitor(SchemeCredentialQuestion.LINK))

    @property
    def get_required_questions(self):
        return self.questions.filter(
            Q(manual_question=True) | Q(scan_question=True) | Q(one_question_link=True)
        ).values('id', 'type')

    def get_question_type_dict(self, question_queryset=None):
        queryset = question_queryset if question_queryset is not None else self.questions.all()
        return {
            question.label: {
                "type": question.type,
                "answer_type": question.answer_type
            }
            for question in queryset
        }

    def __str__(self):
        return '{} ({})'.format(self.name, self.company)


class ConsentsManager(models.Manager):

    def get_queryset(self):
        return super(ConsentsManager, self).get_queryset().exclude(is_enabled=False).order_by('journey', 'order')


class JourneyTypes(IntEnum):
    JOIN = 0
    LINK = 1
    ADD = 2
    UPDATE = 3


class Control(models.Model):
    JOIN_KEY = 'join_button'
    ADD_KEY = 'add_button'

    KEY_CHOICES = (
        (JOIN_KEY, 'Join Button - Add Card screen'),
        (ADD_KEY, 'Add Button - Add Card screen')
    )

    key = models.CharField(max_length=50, choices=KEY_CHOICES)
    label = models.CharField(max_length=50, blank=True)
    hint_text = models.CharField(max_length=250, blank=True)

    scheme = models.ForeignKey(Scheme, related_name="controls", on_delete=models.CASCADE)


class Consent(models.Model):
    journeys = (
        (JourneyTypes.JOIN.value, 'join'),
        (JourneyTypes.LINK.value, 'link'),
        (JourneyTypes.ADD.value, 'add'),
    )

    check_box = models.BooleanField()
    text = models.TextField()
    scheme = models.ForeignKey(Scheme, related_name="consents", on_delete=models.CASCADE)
    is_enabled = models.BooleanField(default=True)
    required = models.BooleanField()
    order = models.IntegerField()
    journey = models.IntegerField(choices=journeys)
    slug = models.SlugField(max_length=50, help_text="Slug must match the opt-in field name in the request"
                                                     " sent to the merchant e.g marketing_opt_in")
    created_on = models.DateTimeField(auto_now_add=True)
    modified_on = models.DateTimeField(auto_now=True)

    objects = ConsentsManager()
    all_objects = models.Manager()

    @property
    def short_text(self):
        return truncatewords(self.text, 5)

    def __str__(self):
        return '({}) {}: {}'.format(self.scheme.slug, self.id, self.short_text)

    class Meta:
        unique_together = ('slug', 'scheme', 'journey')


class Exchange(models.Model):
    donor_scheme = models.ForeignKey('scheme.Scheme', related_name='donor_in', on_delete=models.CASCADE)
    host_scheme = models.ForeignKey('scheme.Scheme', related_name='host_in', on_delete=models.CASCADE)

    exchange_rate_donor = models.IntegerField(default=1)
    exchange_rate_host = models.IntegerField(default=1)

    transfer_min = models.DecimalField(default=0.0, decimal_places=2, max_digits=12, null=True, blank=True)
    transfer_max = models.DecimalField(decimal_places=2, max_digits=12, null=True, blank=True)
    transfer_multiple = models.DecimalField(decimal_places=2, max_digits=12, null=True, blank=True)

    tip_in_url = models.URLField()
    info_url = models.URLField()

    flag_auto_tip_in = models.IntegerField(choices=((0, 'No'), (1, 'Yes')))

    transaction_reference = models.CharField(max_length=24, default='Convert', editable=False)

    start_date = models.DateField(null=True, blank=True, editable=False)
    end_date = models.DateField(null=True, blank=True, editable=False)

    def __str__(self):
        return '{} -> {}'.format(self.donor_scheme.name, self.host_scheme.name)


class ActiveSchemeImageManager(models.Manager):

    def get_queryset(self):
        return super().get_queryset().filter(
            start_date__lt=timezone.now()).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=timezone.now())).exclude(status=Image.DRAFT)


class SchemeImage(Image):
    objects = ActiveSchemeImageManager()
    scheme = models.ForeignKey('scheme.Scheme', related_name='images', on_delete=models.CASCADE)


class SchemeAccountImage(Image):
    objects = ActiveSchemeImageManager()
    scheme = models.ForeignKey('scheme.Scheme', null=True, blank=True, on_delete=models.SET_NULL)
    scheme_accounts = models.ManyToManyField('scheme.SchemeAccount', related_name='scheme_accounts_set')

    def __str__(self):
        return self.description


class ActiveSchemeIgnoreQuestionManager(BulkUpdateManager):
    use_in_migrations = True

    def get_queryset(self):
        return super(ActiveSchemeIgnoreQuestionManager, self).get_queryset().exclude(is_deleted=True)


class SchemeAccount(models.Model):
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
    ENROL_FAILED = 901
    REGISTRATION_FAILED = 902

    EXTENDED_STATUSES = (
        (PENDING, 'Pending', 'PENDING'),
        (ACTIVE, 'Active', 'ACTIVE'),
        (INVALID_CREDENTIALS, 'Invalid credentials', 'INVALID_CREDENTIALS'),
        (INVALID_MFA, 'Invalid mfa', 'INVALID_MFA'),
        (END_SITE_DOWN, 'End site down', 'END_SITE_DOWN'),
        (IP_BLOCKED, 'IP blocked', 'IP_BLOCKED'),
        (TRIPPED_CAPTCHA, 'Tripped captcha', 'TRIPPED_CAPTCHA'),
        (INCOMPLETE, 'Please check your scheme account login details.', 'INCOMPLETE'),
        (LOCKED_BY_ENDSITE, 'Account locked on end site', 'LOCKED_BY_ENDSITE'),
        (RETRY_LIMIT_REACHED, 'Cannot connect, too many retries', 'RETRY_LIMIT_REACHED'),
        (RESOURCE_LIMIT_REACHED, 'Too many balance requests running', 'RESOURCE_LIMIT_REACHED'),
        (UNKNOWN_ERROR, 'An unknown error has occurred', 'UNKNOWN_ERROR'),
        (MIDAS_UNREACHABLE, 'Midas unavailable', 'MIDAS_UNREACHABLE'),
        (WALLET_ONLY, 'Wallet only card', 'WALLET_ONLY'),
        (AGENT_NOT_FOUND, 'Agent does not exist on midas', 'AGENT_NOT_FOUND'),
        (PASSWORD_EXPIRED, 'Password expired', 'PASSWORD_EXPIRED'),
        (JOIN, 'Join', 'JOIN'),
        (NO_SUCH_RECORD, 'No user currently found', 'NO_SUCH_RECORD'),
        (CONFIGURATION_ERROR, 'Error with the configuration or it was not possible to retrieve', 'CONFIGURATION_ERROR'),
        (NOT_SENT, 'Request was not sent', 'NOT_SENT'),
        (ACCOUNT_ALREADY_EXISTS, 'Account already exists', 'ACCOUNT_ALREADY_EXISTS'),
        (SERVICE_CONNECTION_ERROR, 'Service connection error', 'SERVICE_CONNECTION_ERROR'),
        (VALIDATION_ERROR, 'Failed validation', 'VALIDATION_ERROR'),
        (PRE_REGISTERED_CARD, 'Pre-registered card', 'PRE_REGISTERED_CARD'),
        (FAILED_UPDATE, 'Update failed. Delete and re-add card.', 'FAILED_UPDATE'),
        (PENDING_MANUAL_CHECK, 'Pending manual check.', 'PENDING_MANUAL_CHECK'),
        (CARD_NUMBER_ERROR, 'Invalid card_number', 'CARD_NUMBER_ERROR'),
        (LINK_LIMIT_EXCEEDED, 'You can only Link one card per day.', 'LINK_LIMIT_EXCEEDED'),
        (CARD_NOT_REGISTERED, 'Unknown Card number', 'CARD_NOT_REGISTERED'),
        (GENERAL_ERROR, 'General Error such as incorrect user details', 'GENERAL_ERROR'),
        (JOIN_IN_PROGRESS, 'Join in progress', 'JOIN_IN_PROGRESS'),
        (JOIN_ERROR, 'A system error occurred during join', 'JOIN_ERROR'),
        (SCHEME_REQUESTED_DELETE, 'The scheme has requested this account should be deleted', 'SCHEME_REQUESTED_DELETE'),
        (JOIN_ASYNC_IN_PROGRESS, 'Asynchronous join in progress', 'JOIN_ASYNC_IN_PROGRESS'),
        (ENROL_FAILED, 'Enrol Failed', 'ENROL_FAILED'),
        (REGISTRATION_FAILED, 'Ghost Card Registration Failed', 'REGISTRATION_FAILED'),
    )
    STATUSES = tuple(extended_status[:2] for extended_status in EXTENDED_STATUSES)
    JOIN_ACTION_REQUIRED = [JOIN, CARD_NOT_REGISTERED, PRE_REGISTERED_CARD, REGISTRATION_FAILED, ENROL_FAILED,
                            ACCOUNT_ALREADY_EXISTS]
    USER_ACTION_REQUIRED = [INVALID_CREDENTIALS, INVALID_MFA, INCOMPLETE, LOCKED_BY_ENDSITE, VALIDATION_ERROR,
                            PRE_REGISTERED_CARD, REGISTRATION_FAILED, CARD_NUMBER_ERROR, LINK_LIMIT_EXCEEDED,
                            GENERAL_ERROR, JOIN_IN_PROGRESS, SCHEME_REQUESTED_DELETE, FAILED_UPDATE]
    SYSTEM_ACTION_REQUIRED = [END_SITE_DOWN, RETRY_LIMIT_REACHED, UNKNOWN_ERROR, MIDAS_UNREACHABLE,
                              IP_BLOCKED, TRIPPED_CAPTCHA, NO_SUCH_RECORD, RESOURCE_LIMIT_REACHED,
                              CONFIGURATION_ERROR, NOT_SENT, SERVICE_CONNECTION_ERROR, JOIN_ERROR, AGENT_NOT_FOUND]
    EXCLUDE_BALANCE_STATUSES = JOIN_ACTION_REQUIRED + USER_ACTION_REQUIRED + [PENDING, PENDING_MANUAL_CHECK]
    JOIN_EXCLUDE_BALANCE_STATUSES = [PENDING_MANUAL_CHECK, JOIN, JOIN_ASYNC_IN_PROGRESS, ENROL_FAILED]

    user_set = models.ManyToManyField('user.CustomUser', through='ubiquity.SchemeAccountEntry',
                                      related_name='scheme_account_set')
    scheme = models.ForeignKey('scheme.Scheme', on_delete=models.PROTECT)
    status = models.IntegerField(default=PENDING, choices=STATUSES)
    order = models.IntegerField()
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    link_date = models.DateTimeField(null=True, blank=True)
    join_date = models.DateTimeField(null=True, blank=True)
    all_objects = models.Manager()
    objects = ActiveSchemeIgnoreQuestionManager()

    # ubiquity fields
    balances = JSONField(default=dict, null=True, blank=True)
    vouchers = JSONField(default=dict, null=True, blank=True)
    card_number = models.CharField(max_length=250, blank=True, default='')
    barcode = models.CharField(max_length=250, blank=True, default='')
    transactions = JSONField(default=dict, null=True, blank=True)

    @property
    def status_name(self):
        return dict(self.STATUSES).get(self.status)

    @property
    def status_key(self):
        status_keys = dict(
            (extended_status[0], extended_status[2])
            for extended_status
            in self.EXTENDED_STATUSES
        )
        return status_keys.get(self.status)

    def _collect_credentials(self):
        credentials = {}
        for question in self.scheme.questions.all():
            # attempt to get the answer from the database.
            answer = self._find_answer(question.type)
            if not answer:
                continue

            if question.type in ENCRYPTED_CREDENTIALS:
                credentials[question.type] = AESCipher(settings.LOCAL_AES_KEY.encode()).decrypt(answer)
            else:
                credentials[question.type] = answer
        return credentials

    def missing_credentials(self, credential_types):
        """
        Given a list of credential_types return credentials if they are required by the scheme

        A scan or manual question is an optional if one of the other exists
        """
        questions = self.scheme.questions.filter(
            options__in=[F('options').bitor(SchemeCredentialQuestion.LINK), SchemeCredentialQuestion.NONE])

        required_credentials = {question.type for question in questions}
        manual_question = self.scheme.manual_question
        scan_question = self.scheme.scan_question

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

    def get_auth_fields(self):
        credentials = self._collect_credentials()
        link_fields = [field.type for field in self.scheme.link_questions]
        return {
            k: v
            for k, v in credentials.items()
            if k in link_fields
        }

    def credentials(self):
        credentials = self._collect_credentials()
        if self.missing_credentials(credentials.keys()) and self.status != SchemeAccount.PENDING:
            # temporary fix for iceland
            if self.scheme.slug != 'iceland-bonus-card':
                bink_users = [user for user in self.user_set.all() if user.client_id == settings.BINK_CLIENT_ID]
                for user in bink_users:
                    update_scheme_account_attribute_new_status(
                        self,
                        user,
                        dict(self.STATUSES).get(SchemeAccount.INCOMPLETE)
                    )
                self.status = SchemeAccount.INCOMPLETE
                self.save()
                return None

        saved_consents = self.collect_pending_consents()
        credentials.update(consents=saved_consents)

        serialized_credentials = json.dumps(credentials)
        return AESCipher(settings.AES_KEY.encode()).encrypt(serialized_credentials).decode('utf-8')

    def update_or_create_primary_credentials(self, credentials):
        """
        Creates or updates scheme account credential answer objects for manual or scan questions. If only one is
        given and the scheme has a regex conversion for the property, both will be saved.
        :param credentials: dict of credentials
        :return: credentials
        """
        new_credentials = {
            question['type']: credentials.get(question['type'])
            for question in self.scheme.get_required_questions
        }

        for k, v in new_credentials.items():
            if v:
                SchemeAccountCredentialAnswer.objects.update_or_create(
                    question=self.question(k),
                    scheme_account=self,
                    defaults={'answer': v})

        self.update_barcode_and_card_number()
        for question in ['card_number', 'barcode']:
            value = getattr(self, question)
            if not credentials.get(question) and value:
                credentials.update({question: value})

        return credentials

    def collect_pending_consents(self):
        user_consents = self.userconsent_set.filter(status=ConsentStatus.PENDING).values()
        formatted_user_consents = []
        for user_consent in user_consents:
            formatted_user_consents.append(
                {
                    "id": user_consent['id'],
                    "slug": user_consent['slug'],
                    "value": user_consent['value'],
                    "created_on": arrow.get(user_consent['created_on']).for_json(),
                    "journey_type": user_consent['metadata']['journey']
                }
            )

        return formatted_user_consents

    def _process_midas_response(self, response):
        points = None
        self.status = response.status_code
        if self.status not in [status[0] for status in self.EXTENDED_STATUSES]:
            self.status = SchemeAccount.UNKNOWN_ERROR
        if response.status_code == 200:
            points = response.json()
            self.status = SchemeAccount.PENDING if points.get('pending') else SchemeAccount.ACTIVE
            points['balance'] = points.get('balance')  # serializers.DecimalField does not allow blank fields
            points['is_stale'] = False

            if settings.ENABLE_DAEDALUS_MESSAGING:
                settings.TO_DAEDALUS.send(
                    {"type": 'membership_card_update',
                     "model": 'schemeaccount',
                     "id": str(self.id),
                     "user_set": ','.join([str(u.id) for u in self.user_set.all()]),
                     "rep": repr(self)},
                    headers={'X-content-type': 'application/json'}
                )
        return points

    def get_midas_balance(self, journey):
        points = None
        old_status = self.status

        if self.status in self.JOIN_EXCLUDE_BALANCE_STATUSES:
            return points

        try:
            credentials = self.credentials()
            if not credentials:
                return points
            response = self._get_balance(credentials, journey)
            points = self._process_midas_response(response)

        except ConnectionError:
            self.status = SchemeAccount.MIDAS_UNREACHABLE

        saved = self._received_balance_checks(old_status)
        # Update active_link status
        if self.status != old_status:
            if not saved:
                self.save(update_fields=['status'])
            PaymentCardSchemeEntry.update_active_link_status({'scheme_account': self})
        return points

    def _received_balance_checks(self, old_status):
        saved = False
        if self.status in SchemeAccount.JOIN_ACTION_REQUIRED:
            queryset = self.schemeaccountcredentialanswer_set
            card_number = self.card_number
            if card_number:
                queryset = queryset.exclude(answer=card_number)

            queryset.all().delete()

        if self.status != SchemeAccount.PENDING:
            self.save(update_fields=['status'])
            saved = True
            self.call_analytics(self.user_set.all(), old_status)
        return saved

    def call_analytics(self, user_set, old_status):
        bink_users = [user for user in user_set if user.client_id == settings.BINK_CLIENT_ID]
        for user in bink_users:  # Update intercom
            update_scheme_account_attribute(self, user, dict(self.STATUSES).get(old_status))

    def _get_balance(self, credentials, journey):
        user_set = ','.join([str(u.id) for u in self.user_set.all()])
        parameters = {
            'scheme_account_id': self.id,
            'credentials': credentials,
            'user_set': user_set,
            'status': self.status,
            'journey_type': journey.value,
        }
        midas_balance_uri = f'{settings.MIDAS_URL}/{self.scheme.slug}/balance'
        headers = {"transaction": str(uuid.uuid1()), "User-agent": 'Hermes on {0}'.format(socket.gethostname())}
        response = requests.get(midas_balance_uri, params=parameters, headers=headers)
        return response

    def get_journey_type(self):
        if self.balances:
            return JourneyTypes.UPDATE
        else:
            return JourneyTypes.LINK

    def _update_cached_balance(self, cache_key):
        journey = self.get_journey_type()
        balance = self.get_midas_balance(journey=journey)
        vouchers = None

        if balance:
            if "vouchers" in balance:
                vouchers = self.make_vouchers_response(balance["vouchers"])
                del balance["vouchers"]

            balance.update({'updated_at': arrow.utcnow().timestamp, 'scheme_id': self.scheme.id})
            cache.set(cache_key, balance, settings.BALANCE_RENEW_PERIOD)

        return balance, vouchers

    def update_barcode_and_card_number(self, scheme_questions=None):
        if scheme_questions is not None:
            questions_ids = {
                question.type: question.id
                for question in scheme_questions
                if question.type in [CARD_NUMBER, BARCODE]
            }
        else:
            questions_ids = {
                question['type']: question['id']
                for question in self.scheme.questions.filter(type__in=[CARD_NUMBER, BARCODE]).values('type', 'id')
            }

        self._update_card_number(questions_ids)
        self._update_barcode(questions_ids)
        self.save(update_fields=['barcode', 'card_number'])

    def get_cached_balance(self, user_consents=None):
        cache_key = 'scheme_{}'.format(self.pk)
        balance = cache.get(cache_key)
        vouchers = None  # should we cache these too?

        if not balance:
            balance, vouchers = self._update_cached_balance(cache_key)

        needs_save = False

        if balance != self.balances and balance:
            self.balances = [{k: float(v) if isinstance(v, Decimal) else v for k, v in balance.items()}]
            needs_save = True

        if vouchers != self.vouchers and vouchers:
            self.vouchers = vouchers
            needs_save = True

        if needs_save:
            self.save(update_fields=['balances', 'vouchers'])

        return balance

    def make_vouchers_response(self, vouchers: list):
        """
        Vouchers come from Midas with the following fields:
        * issue_date: int, optional
        * redeem_date: int, optional
        * expiry_date: int, optional
        * code: str, optional
        * type: int, required
        * value: Decimal, optional
        * target_value: Decimal, optional
        """
        return [
            self.make_single_voucher(voucher_fields) for voucher_fields in vouchers
        ]

    def make_single_voucher(self, voucher_fields):
        voucher_type = vouchers.VoucherType(voucher_fields["type"])

        # this can fail with a VoucherScheme.DoesNotExist if the configuration is incorrect
        # i let this exception go as this is something we would want to know about & fix in the database.
        voucher_scheme = VoucherScheme.objects.get(
            scheme=self.scheme,
            earn_type=VoucherScheme.earn_type_from_voucher_type(voucher_type),
        )

        issue_date = arrow.get(voucher_fields["issue_date"]) if "issue_date" in voucher_fields else None
        redeem_date = arrow.get(voucher_fields["redeem_date"]) if "redeem_date" in voucher_fields else None

        expiry_date = vouchers.get_expiry_date(voucher_scheme, voucher_fields, issue_date)
        state = vouchers.guess_voucher_state(issue_date, redeem_date, expiry_date)

        headline_template = voucher_scheme.get_headline(state)
        headline = vouchers.apply_template(
            headline_template,
            voucher_scheme=voucher_scheme,
            earn_value=voucher_fields.get("value", 0),
            earn_target_value=voucher_fields.get("target_value", 0),
        )

        body_text = voucher_scheme.get_body_text(state)

        voucher = {
            "state": vouchers.voucher_state_names[state],
            "earn": {
                "type": vouchers.voucher_type_names[voucher_type],
                "prefix": voucher_scheme.earn_prefix,
                "suffix": voucher_scheme.earn_suffix,
                "currency": voucher_scheme.earn_currency,
                "value": voucher_fields.get("value", 0),
                "target_value": voucher_fields.get("target_value", 0),
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
            voucher.update({
                "date_issued": issue_date.timestamp,
                "expiry_date": expiry_date.timestamp,
            })

        if redeem_date is not None:
            voucher["date_redeemed"] = redeem_date.timestamp

        if "code" in voucher_fields:
            voucher["code"] = voucher_fields["code"]

        return voucher

    def set_pending(self, manual_pending: bool = False) -> None:
        self.status = SchemeAccount.PENDING_MANUAL_CHECK if manual_pending else SchemeAccount.PENDING
        self.save(update_fields=['status'])

    def set_async_join_status(self) -> None:
        self.status = SchemeAccount.JOIN_ASYNC_IN_PROGRESS
        self.save()

    def delete_cached_balance(self):
        cache_key = 'scheme_{}'.format(self.pk)
        cache.delete(cache_key)

    def delete_saved_balance(self):
        self.balances = dict()
        self.save()

    def question(self, question_type):
        """
        Return the scheme question instance for the given question type
        :param question_type:
        :return:
        """
        return SchemeCredentialQuestion.objects.filter(type=question_type, scheme=self.scheme).first()

    @property
    def card_label(self):
        manual_answer = self.manual_answer
        if self.manual_answer:
            return manual_answer.answer

        barcode_answer = self.barcode_answer
        if not barcode_answer:
            return None

        if self.scheme.card_number_regex:
            try:
                regex_match = re.search(self.scheme.card_number_regex, barcode_answer.answer)
            except sre_constants.error:
                return None
            if regex_match:
                try:
                    return self.scheme.card_number_prefix + regex_match.group(1)
                except IndexError:
                    return None
        return barcode_answer.answer

    def get_transaction_matching_user_id(self):
        bink_user = self.user_set.filter(client_id=settings.BINK_CLIENT_ID).values('id').order_by('date_joined')
        if bink_user.exists():
            user_id = bink_user.first().get('id')
        else:
            user_id = self.user_set.order_by('date_joined').values('id').first().get('id')

        return user_id

    def _update_barcode(self, questions_ids):
        barcode = self.schemeaccountcredentialanswer_set.filter(
            question__id__in=questions_ids.values()
        ).values('question__type', 'answer').order_by('question__type').first()

        if not barcode:
            self.barcode = ''
            return None

        if barcode['question__type'] == BARCODE:
            self.barcode = barcode['answer']

        elif barcode['question__type'] == CARD_NUMBER and self.scheme.barcode_regex:
            try:
                regex_match = re.search(self.scheme.barcode_regex, barcode['answer'])
            except sre_constants.error:
                self.barcode = ''
                return None
            if regex_match:
                try:
                    self.barcode = self.scheme.barcode_prefix + regex_match.group(1)
                except IndexError:
                    pass

        else:
            self.barcode = ''

    def _update_card_number(self, questions_ids):
        card_number = self.schemeaccountcredentialanswer_set.filter(
            question__id__in=questions_ids.values()
        ).values('question__type', 'answer').order_by('-question__type').first()

        if not card_number:
            self.card_number = ''
            return None

        if card_number['question__type'] == CARD_NUMBER:
            self.card_number = card_number['answer']

        elif card_number['question__type'] == BARCODE and self.scheme.card_number_regex:
            try:
                regex_match = re.search(self.scheme.card_number_regex, card_number['answer'])
            except sre_constants.error:
                self.card_number = ''
                return None
            if regex_match:
                try:
                    self.card_number = self.scheme.card_number_prefix + regex_match.group(1)
                except IndexError:
                    pass

        else:
            self.card_number = ''

    @property
    def barcode_answer(self):
        return self.schemeaccountcredentialanswer_set.filter(question=self.question(BARCODE)).first()

    @property
    def card_number_answer(self):
        return self.schemeaccountcredentialanswer_set.filter(question=self.question(CARD_NUMBER)).first()

    @property
    def manual_answer(self):
        return self.schemeaccountcredentialanswer_set.filter(question=self.scheme.manual_question).first()

    @property
    def one_question_link_answer(self):
        return self.schemeaccountcredentialanswer_set.filter(question=self.scheme.one_question_link).first()

    @property
    def display_status(self):
        # linked accounts in "system account required" should be displayed as "active".
        # accounts in "active", "pending", and "join" statuses should be displayed as such.
        # all other statuses should be displayed as "wallet only"
        if (self.link_date or self.join_date) and self.status in self.SYSTEM_ACTION_REQUIRED:
            return self.ACTIVE
        elif self.status in [self.ACTIVE, self.PENDING, self.JOIN]:
            return self.status
        elif self.status in self.JOIN_ACTION_REQUIRED:
            return self.JOIN
        else:
            return self.WALLET_ONLY

    @property
    def third_party_identifier(self):
        question = SchemeCredentialQuestion.objects.filter(third_party_identifier=True, scheme=self.scheme).first()
        if question:
            return self._find_answer(question.type)

        return None

    def _find_answer(self, question_type):
        # attempt to get the answer from the database.
        answer = None
        answer_instance = self.schemeaccountcredentialanswer_set.filter(question__type=question_type).first()
        if answer_instance:
            answer = answer_instance.answer
        else:
            # see if we have a property that will give us the answer.
            try:
                answer = getattr(self, question_type)
            except AttributeError:
                # we can't get an answer to this question, so skip it.
                pass
        return answer

    def __str__(self):
        return "{} - id: {}".format(self.scheme.name, self.id)

    class Meta:
        ordering = ['order', '-created']


class SchemeCredentialQuestion(models.Model):
    NONE = 0
    LINK = 1 << 0
    JOIN = 1 << 1
    OPTIONAL_JOIN = (1 << 2 | JOIN)
    LINK_AND_JOIN = (LINK | JOIN)
    MERCHANT_IDENTIFIER = (1 << 3)

    OPTIONS = (
        (NONE, 'None'),
        (LINK, 'Link'),
        (JOIN, 'Join'),
        (OPTIONAL_JOIN, 'Join (optional)'),
        (LINK_AND_JOIN, 'Link & Join'),
        (MERCHANT_IDENTIFIER, 'Merchant Identifier')
    )

    # ubiquity choices
    ANSWER_TYPE_CHOICES = (
        (0, 'text'),
        (1, 'sensitive'),
        (2, 'choice'),
        (3, 'boolean'),
        (4, 'payment_card_hash'),
    )

    scheme = models.ForeignKey('Scheme', related_name='questions', on_delete=models.PROTECT)
    order = models.IntegerField(default=0)
    type = models.CharField(max_length=250, choices=CREDENTIAL_TYPES)
    label = models.CharField(max_length=250)
    third_party_identifier = models.BooleanField(default=False)
    manual_question = models.BooleanField(default=False)
    scan_question = models.BooleanField(default=False)
    one_question_link = models.BooleanField(default=False)
    options = models.IntegerField(choices=OPTIONS, default=NONE)

    # ubiquity fields
    validation = models.TextField(default='', blank=True, max_length=250)
    description = models.CharField(default='', blank=True, max_length=250)
    # common_name = models.CharField(default='', blank=True, max_length=50)
    answer_type = models.IntegerField(default=0, choices=ANSWER_TYPE_CHOICES)
    choice = ArrayField(models.CharField(max_length=50), null=True, blank=True)
    add_field = models.BooleanField(default=False)
    auth_field = models.BooleanField(default=False)
    register_field = models.BooleanField(default=False)
    enrol_field = models.BooleanField(default=False)

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
        ordering = ['order']
        unique_together = ("scheme", "type")

    def __str__(self):
        return self.type


class SchemeCredentialQuestionChoice(models.Model):
    scheme = models.ForeignKey('Scheme', on_delete=models.CASCADE)
    scheme_question = models.CharField(max_length=250, choices=CREDENTIAL_TYPES)

    @property
    def values(self):
        choice_values = self.choice_values.all()
        return [str(value) for value in choice_values]

    class Meta:
        unique_together = ("scheme", "scheme_question")


class SchemeCredentialQuestionChoiceValue(models.Model):
    choice = models.ForeignKey('SchemeCredentialQuestionChoice', related_name='choice_values', on_delete=models.CASCADE)
    value = models.CharField(max_length=250)
    order = models.IntegerField(default=0)

    def __str__(self):
        return self.value

    class Meta:
        ordering = ['order', 'value']


class SchemeDetail(models.Model):
    TYPE_CHOICES = (
        (0, 'Tier'),
    )

    scheme_id = models.ForeignKey('Scheme', on_delete=models.CASCADE)
    type = models.IntegerField(choices=TYPE_CHOICES, default=0)
    name = models.CharField(max_length=255)
    description = models.TextField()


class SchemeBalanceDetails(models.Model):
    scheme_id = models.ForeignKey('Scheme', on_delete=models.CASCADE)
    currency = models.CharField(default='', blank=True, max_length=50)
    prefix = models.CharField(default='', blank=True, max_length=50)
    suffix = models.CharField(default='', blank=True, max_length=50)
    description = models.TextField(default='', blank=True, max_length=250)

    class Meta:
        verbose_name_plural = 'balance details'


class SchemeAccountCredentialAnswer(models.Model):
    scheme_account = models.ForeignKey(SchemeAccount, on_delete=models.CASCADE)
    question = models.ForeignKey(SchemeCredentialQuestion, null=True, on_delete=models.PROTECT)
    answer = models.CharField(max_length=250)

    def clean_answer(self):
        if self.question.type in ENCRYPTED_CREDENTIALS:
            return "****"
        return self.answer

    def __str__(self):
        return self.clean_answer()

    class Meta:
        unique_together = ("scheme_account", "question")


@receiver(pre_save, sender=SchemeAccountCredentialAnswer)
def encryption_handler(sender, instance, **kwargs):
    if instance.question.type in ENCRYPTED_CREDENTIALS:
        try:
            encrypted_answer = AESCipher(settings.LOCAL_AES_KEY.encode()).encrypt(instance.answer).decode("utf-8")
        except AttributeError:
            answer = str(instance.answer)
            encrypted_answer = AESCipher(settings.LOCAL_AES_KEY.encode()).encrypt(answer).decode("utf-8")

        instance.answer = encrypted_answer


class ConsentStatus(IntEnum):
    PENDING = 0
    SUCCESS = 1
    FAILED = 2


class UserConsent(models.Model):
    created_on = models.DateTimeField(default=timezone.now)
    user = models.ForeignKey('user.CustomUser', null=True, on_delete=models.SET_NULL)
    scheme = models.ForeignKey(Scheme, null=True, on_delete=models.SET_NULL)
    scheme_account = models.ForeignKey(SchemeAccount, null=True, on_delete=models.SET_NULL)
    metadata = JSONField()
    slug = models.SlugField(max_length=50)
    value = models.BooleanField()
    status = models.IntegerField(choices=[(status.value, status.name) for status in ConsentStatus],
                                 default=ConsentStatus.PENDING)

    @property
    def short_text(self):
        metadata = dict(self.metadata)
        return truncatewords(metadata.get('text'), 5)

    def __str__(self):
        return '{} - {}: {}'.format(self.user, self.slug, self.value)


class ThirdPartyConsentLink(models.Model):
    consent_label = models.CharField(max_length=50)
    client_app = models.ForeignKey('user.ClientApplication', related_name='client_app', on_delete=models.CASCADE)
    scheme = models.ForeignKey('scheme.Scheme', related_name='scheme', on_delete=models.CASCADE)
    consent = models.ForeignKey(Consent, related_name='consent', on_delete=models.CASCADE)

    add_field = models.BooleanField(default=False)
    auth_field = models.BooleanField(default=False)
    register_field = models.BooleanField(default=False)
    enrol_field = models.BooleanField(default=False)


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

    scheme = models.ForeignKey("scheme.Scheme", on_delete=models.CASCADE)

    earn_currency = models.CharField(max_length=50, blank=True, verbose_name="Currency")
    earn_prefix = models.CharField(max_length=50, blank=True, verbose_name="Prefix")
    earn_suffix = models.CharField(max_length=50, blank=True, verbose_name="Suffix")
    earn_type = models.CharField(max_length=50, choices=EARN_TYPES, verbose_name="Earn Type")

    burn_currency = models.CharField(max_length=50, blank=True, verbose_name="Currency")
    burn_prefix = models.CharField(max_length=50, blank=True, verbose_name="Prefix")
    burn_suffix = models.CharField(max_length=50, blank=True, verbose_name="Suffix")
    burn_type = models.CharField(max_length=50, choices=BURN_TYPES, verbose_name="Burn Type")
    burn_value = models.FloatField(blank=True, null=True, verbose_name="Value")

    barcode_type = models.IntegerField(choices=BARCODE_TYPES)

    headline_inprogress = models.CharField(max_length=250, verbose_name="In Progress")
    headline_expired = models.CharField(max_length=250, verbose_name="Expired")
    headline_redeemed = models.CharField(max_length=250, verbose_name="Redeemed")
    headline_issued = models.CharField(max_length=250, verbose_name="Issued")

    body_text_inprogress = models.TextField(null=False, blank=True, verbose_name="In Progress")
    body_text_expired = models.TextField(null=False, blank=True, verbose_name="Expired")
    body_text_redeemed = models.TextField(null=False, blank=True, verbose_name="Redeemed")
    body_text_issued = models.TextField(null=False, blank=True, verbose_name="Issued")
    subtext = models.CharField(max_length=250, null=False, blank=True)
    terms_and_conditions_url = models.URLField(null=False, blank=True)

    expiry_months = models.IntegerField()

    def __str__(self):
        type_name = dict(self.EARN_TYPES)[self.earn_type]
        return "{} {} - id: {}".format(self.scheme.name, type_name, self.id)

    def get_headline(self, state: vouchers.VoucherState):
        return {
            vouchers.VoucherState.ISSUED: self.headline_issued,
            vouchers.VoucherState.IN_PROGRESS: self.headline_inprogress,
            vouchers.VoucherState.EXPIRED: self.headline_expired,
            vouchers.VoucherState.REDEEMED: self.headline_redeemed,
        }[state]

    def get_body_text(self, state: vouchers.VoucherState):
        return {
            vouchers.VoucherState.ISSUED: self.body_text_issued,
            vouchers.VoucherState.IN_PROGRESS: self.body_text_inprogress,
            vouchers.VoucherState.EXPIRED: self.body_text_expired,
            vouchers.VoucherState.REDEEMED: self.body_text_redeemed,
        }[state]

    @staticmethod
    def earn_type_from_voucher_type(voucher_type: vouchers.VoucherType):
        return {
            vouchers.VoucherType.JOIN: VoucherScheme.EARNTYPE_JOIN,
            vouchers.VoucherType.ACCUMULATOR: VoucherScheme.EARNTYPE_ACCUMULATOR,
            vouchers.VoucherType.STAMPS: VoucherScheme.EARNTYPE_STAMPS,
        }[voucher_type]
