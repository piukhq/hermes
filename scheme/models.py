import json
import re
import socket
import sre_constants
import uuid
from decimal import Decimal
from enum import IntEnum

import arrow
from bulk_update.manager import BulkUpdateManager
from colorful.fields import RGBColorField
from django.conf import settings
from django.contrib.postgres.fields import ArrayField, JSONField
from django.core.cache import cache
from django.db import models
from django.db.models import F, Q
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.template.defaultfilters import truncatewords
from django.utils import timezone

from analytics.api import update_scheme_account_attribute_new_status, update_scheme_account_attribute
from common.models import Image
from hermes.traced_requests import requests
from scheme.credentials import BARCODE, CARD_NUMBER, CREDENTIAL_TYPES, ENCRYPTED_CREDENTIALS
from scheme.encyption import AESCipher


class Category(models.Model):
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name


class ActiveSchemeManager(models.Manager):

    def get_queryset(self):
        return super().get_queryset().exclude(status=Scheme.INACTIVE)


def _default_transaction_headers():
    return ["Date", "Reference", "Points"]


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
    MAX_POINTS_VALUE_LENGTHS = (
        (0, '0 (no numeric points value)'),
        (1, '1 (0-9)'),
        (2, '2 (0-99)'),
        (3, '3 (0-999)'),
        (4, '4 (0+)'),
    )
    MAX_POINTS_VALUE_LENGTH = 11

    ACTIVE = 0
    SUSPENDED = 1
    INACTIVE = 2
    STATUSES = (
        (ACTIVE, 'Active'),
        (SUSPENDED, 'Suspended'),
        (INACTIVE, 'Inactive'),
    )

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
    status = models.IntegerField(choices=STATUSES, default=ACTIVE)
    category = models.ForeignKey(Category)

    card_number_regex = models.CharField(max_length=100, blank=True,
                                         help_text="Regex to map barcode to card number")
    barcode_regex = models.CharField(max_length=100, blank=True,
                                     help_text="Regex to map card number to barcode")
    card_number_prefix = models.CharField(max_length=100, blank=True,
                                          help_text="Prefix to from barcode -> card number mapping")
    barcode_prefix = models.CharField(max_length=100, blank=True,
                                      help_text="Prefix to from card number -> barcode mapping")
    all_objects = models.Manager()
    objects = ActiveSchemeManager()

    # ubiquity fields
    authorisation_required = models.BooleanField(default=False)
    digital_only = models.BooleanField(default=False)
    plan_name = models.CharField(max_length=50, null=True, blank=True)
    plan_name_card = models.CharField(max_length=50, null=True, blank=True)
    plan_summary = models.TextField(default='', blank=True, max_length=250)
    plan_description = models.TextField(default='', blank=True, max_length=500)
    enrol_incentive = models.CharField(max_length=50, null=True, blank=True)

    @property
    def is_active(self):
        return self.status != self.INACTIVE

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

    def get_question_type_dict(self):
        return {
            question.label: question.type
            for question in self.questions.all()
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

    scheme = models.ForeignKey(Scheme, related_name="controls")


class Consent(models.Model):
    journeys = (
        (JourneyTypes.JOIN.value, 'join'),
        (JourneyTypes.LINK.value, 'link'),
        (JourneyTypes.ADD.value, 'add'),
    )

    check_box = models.BooleanField()
    text = models.TextField()
    scheme = models.ForeignKey(Scheme, related_name="consents")
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
    donor_scheme = models.ForeignKey('scheme.Scheme', related_name='donor_in')
    host_scheme = models.ForeignKey('scheme.Scheme', related_name='host_in')

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
    scheme = models.ForeignKey('scheme.Scheme', related_name='images')


class SchemeAccountImage(Image):
    objects = ActiveSchemeImageManager()
    scheme = models.ForeignKey('scheme.Scheme', null=True, blank=True)
    scheme_accounts = models.ManyToManyField('scheme.SchemeAccount', related_name='scheme_accounts_set')

    def __str__(self):
        return self.description


class ActiveSchemeIgnoreQuestionManager(BulkUpdateManager):
    use_in_migrations = True

    def get_queryset(self):
        return super(ActiveSchemeIgnoreQuestionManager, self).get_queryset().exclude(is_deleted=True). \
            exclude(scheme__status=Scheme.INACTIVE)


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
    PENDING_MANUAL_CHECK = 204
    CARD_NUMBER_ERROR = 436
    LINK_LIMIT_EXCEEDED = 437
    CARD_NOT_REGISTERED = 438
    GENERAL_ERROR = 439
    JOIN_IN_PROGRESS = 441
    JOIN_ERROR = 538

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
        (JOIN_ERROR, 'A system error occurred during join', 'JOIN_ERROR')
    )
    STATUSES = tuple(extended_status[:2] for extended_status in EXTENDED_STATUSES)
    JOIN_ACTION_REQUIRED = [JOIN, CARD_NOT_REGISTERED, PRE_REGISTERED_CARD]
    USER_ACTION_REQUIRED = [INVALID_CREDENTIALS, INVALID_MFA, INCOMPLETE, LOCKED_BY_ENDSITE, VALIDATION_ERROR,
                            ACCOUNT_ALREADY_EXISTS, PRE_REGISTERED_CARD, CARD_NUMBER_ERROR, LINK_LIMIT_EXCEEDED,
                            GENERAL_ERROR, JOIN_IN_PROGRESS]
    SYSTEM_ACTION_REQUIRED = [END_SITE_DOWN, RETRY_LIMIT_REACHED, UNKNOWN_ERROR, MIDAS_UNREACHABLE,
                              IP_BLOCKED, TRIPPED_CAPTCHA, NO_SUCH_RECORD, RESOURCE_LIMIT_REACHED,
                              CONFIGURATION_ERROR, NOT_SENT, SERVICE_CONNECTION_ERROR, JOIN_ERROR]

    user_set = models.ManyToManyField('user.CustomUser', through='ubiquity.SchemeAccountEntry',
                                      related_name='scheme_account_set')
    scheme = models.ForeignKey('scheme.Scheme')
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
    balances = JSONField(default=dict(), null=True, blank=True)

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
        manual_question = self.scheme.manual_question
        manual_answer = None
        if manual_question:
            manual_answer = credentials.get(manual_question.type)

        scan_question = self.scheme.scan_question
        scan_answer = None
        if scan_question:
            scan_answer = credentials.get(scan_question.type)

        if manual_question and manual_answer:
            SchemeAccountCredentialAnswer.objects.update_or_create(
                question=self.question(manual_question.type),
                scheme_account=self,
                defaults={'answer': credentials[manual_question.type]})

        if scan_question and scan_answer:
            SchemeAccountCredentialAnswer.objects.update_or_create(
                question=self.question(scan_question.type),
                scheme_account=self,
                defaults={'answer': credentials[scan_question.type]})

        regex_credentials = [
            'card_number',
            'barcode'
        ]
        for question in regex_credentials:
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

    def get_midas_balance(self, journey):
        points = None
        old_status = self.status

        if self.status == SchemeAccount.PENDING_MANUAL_CHECK:
            return points

        try:
            credentials = self.credentials()
            if not credentials:
                return points
            response = self._get_balance(credentials, journey)
            self.status = response.status_code
            if self.status not in [status[0] for status in self.EXTENDED_STATUSES]:
                self.status = SchemeAccount.UNKNOWN_ERROR
            if response.status_code == 200:
                points = response.json()
                self.status = SchemeAccount.PENDING if points.get('pending') else SchemeAccount.ACTIVE
                points['balance'] = points.get('balance')  # serializers.DecimalField does not allow blank fields
                points['is_stale'] = False
        except ConnectionError:
            self.status = SchemeAccount.MIDAS_UNREACHABLE

        self._received_balance_checks(old_status)
        return points

    def _received_balance_checks(self, old_status):
        if self.status in SchemeAccount.JOIN_ACTION_REQUIRED:
            queryset = self.schemeaccountcredentialanswer_set
            card_number = self.card_number
            if card_number:
                queryset = queryset.exclude(answer=card_number)

            queryset.all().delete()

        if self.status != SchemeAccount.PENDING:
            self.save()
            self.call_analytics(self.user_set.all(), old_status)

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
        headers = {"transaction": str(uuid.uuid1()), "User-agent": 'Hermes on {0}'.format(socket.gethostname())}
        response = requests.get('{}/{}/balance'.format(settings.MIDAS_URL, self.scheme.slug),
                                params=parameters, headers=headers)
        return response

    def get_cached_balance(self, user_consents=None):
        cache_key = 'scheme_{}'.format(self.pk)
        balance = cache.get(cache_key)

        if not balance:
            balance = self.get_midas_balance(journey=JourneyTypes.UPDATE)
            if balance:
                balance.update({'updated_at': arrow.utcnow().timestamp, 'scheme_id': self.scheme.id})
                cache.set(cache_key, balance, settings.BALANCE_RENEW_PERIOD)

        if balance != self.balances and balance:
            self.balances = [{k: float(v) if isinstance(v, Decimal) else v for k, v in balance.items()}]
            self.save()

        return balance

    def set_pending(self, manual_pending=False):
        self.status = SchemeAccount.PENDING_MANUAL_CHECK if manual_pending else SchemeAccount.PENDING
        self.save()

    def delete_cached_balance(self):
        cache_key = 'scheme_{}'.format(self.pk)
        cache.delete(cache_key)

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

    @property
    def card_number(self):
        card_number_answer = self.card_number_answer
        if card_number_answer:
            return card_number_answer.answer

        barcode = self.barcode_answer
        if barcode and self.scheme.card_number_regex:
            try:
                regex_match = re.search(self.scheme.card_number_regex, barcode.answer)
            except sre_constants.error:
                return None
            if regex_match:
                try:
                    return self.scheme.card_number_prefix + regex_match.group(1)
                except IndexError:
                    return None
        return None

    def get_transaction_matching_user_id(self):
        bink_user = self.user_set.filter(client_id=settings.BINK_CLIENT_ID).values('id').order_by('date_joined')
        if bink_user.exists():
            user_id = bink_user.first().get('id')
        else:
            user_id = self.user_set.order_by('date_joined').values('id').first().get('id')

        return user_id

    @property
    def barcode(self):
        barcode_answer = self.barcode_answer
        if barcode_answer:
            return barcode_answer.answer

        card_number = self.card_number_answer
        if card_number and self.scheme.barcode_regex:
            try:
                regex_match = re.search(self.scheme.barcode_regex, card_number.answer)
            except sre_constants.error:
                return None
            if regex_match:
                try:
                    return self.scheme.barcode_prefix + regex_match.group(1)
                except IndexError:
                    return None
        return None

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

    scheme_id = models.ForeignKey('Scheme')
    type = models.IntegerField(choices=TYPE_CHOICES, default=0)
    name = models.CharField(max_length=255)
    description = models.TextField()


class SchemeBalanceDetails(models.Model):
    scheme_id = models.ForeignKey('Scheme')
    currency = models.CharField(default='', blank=True, max_length=50)
    prefix = models.CharField(default='', blank=True, max_length=50)
    suffix = models.CharField(default='', blank=True, max_length=50)
    description = models.TextField(default='', blank=True, max_length=250)

    class Meta:
        verbose_name_plural = 'balance details'


class SchemeAccountCredentialAnswer(models.Model):
    scheme_account = models.ForeignKey(SchemeAccount)
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
