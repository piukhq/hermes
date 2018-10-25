import json
import re
import socket
import sre_constants
import uuid
from decimal import Decimal
from enum import Enum, IntEnum

import arrow
import requests
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

from common.models import Image
from scheme.credentials import BARCODE, CARD_NUMBER, CREDENTIAL_TYPES, ENCRYPTED_CREDENTIALS
from scheme.encyption import AESCipher


class Category(models.Model):
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name


class ActiveSchemeManager(models.Manager):

    def get_queryset(self):
        schemes = super(ActiveSchemeManager, self).get_queryset().exclude(is_active=False)
        schemes_without_questions = []
        for scheme in schemes:
            if len(scheme.questions.all()) == 0:
                schemes_without_questions.append(scheme.id)
        return schemes.exclude(id__in=schemes_without_questions)


def _default_transaction_headers():
    return ["Date", "Reference", "Points"]


class Scheme(models.Model):
    TIERS = (
        (1, 'PLL'),
        (2, 'Basic'),
        (3, 'Partner'),
    )
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
    is_active = models.BooleanField(default=True)
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
            for question in self.questions.filter(field_type__isnull=False).all()
        }

    def __str__(self):
        return '{} ({})'.format(self.name, self.company)


class ConsentsManager(models.Manager):

    def get_queryset(self):
        return super(ConsentsManager, self).get_queryset().exclude(is_enabled=False).order_by('journey', 'order')


class JourneyTypes(Enum):
    JOIN = 0
    LINK = 1
    ADD = 2


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
            exclude(scheme__is_active=False)


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
    FAILED_UPDATE = 600

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
        (FAILED_UPDATE, 'Update failed. Delete and re-add card.', 'FAILED_UPDATE')
    )
    STATUSES = tuple(extended_status[:2] for extended_status in EXTENDED_STATUSES)
    USER_ACTION_REQUIRED = [INVALID_CREDENTIALS, INVALID_MFA, INCOMPLETE, LOCKED_BY_ENDSITE, VALIDATION_ERROR,
                            ACCOUNT_ALREADY_EXISTS]
    SYSTEM_ACTION_REQUIRED = [END_SITE_DOWN, RETRY_LIMIT_REACHED, UNKNOWN_ERROR, MIDAS_UNREACHABLE,
                              IP_BLOCKED, TRIPPED_CAPTCHA, PENDING, NO_SUCH_RECORD, RESOURCE_LIMIT_REACHED,
                              CONFIGURATION_ERROR, NOT_SENT, SERVICE_CONNECTION_ERROR]

    user_set = models.ManyToManyField('user.CustomUser', through='ubiquity.SchemeAccountEntry',
                                      related_name='scheme_account_set')
    scheme = models.ForeignKey('scheme.Scheme')
    status = models.IntegerField(default=PENDING, choices=STATUSES)
    order = models.IntegerField()
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    link_date = models.DateTimeField(null=True, blank=True)
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

    def credentials(self, user_consents=None):
        credentials = self._collect_credentials()
        if self.missing_credentials(credentials.keys()) and self.status != SchemeAccount.PENDING:
            self.status = SchemeAccount.INCOMPLETE
            self.save()
            return None

        if user_consents is not None:
            credentials.update(consents=user_consents)

        serialized_credentials = json.dumps(credentials)
        return AESCipher(settings.AES_KEY.encode()).encrypt(serialized_credentials).decode('utf-8')

    def get_midas_balance(self, user_consents=None):
        points = None
        try:
            credentials = self.credentials(user_consents)
            if not credentials:
                return points
            response = self._get_balance(credentials)
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
        if self.status != SchemeAccount.PENDING:
            self.save()
        return points

    def _get_balance(self, credentials):
        user_set = ','.join([str(u.id) for u in self.user_set.all()])
        parameters = {
            'scheme_account_id': self.id,
            'credentials': credentials,
            'user_set': user_set,
            'status': self.status,
            'journey_type': JourneyTypes.LINK.value,
        }
        headers = {"transaction": str(uuid.uuid1()), "User-agent": 'Hermes on {0}'.format(socket.gethostname())}
        response = requests.get('{}/{}/balance'.format(settings.MIDAS_URL, self.scheme.slug),
                                params=parameters, headers=headers)
        return response

    def get_cached_balance(self, user_consents=None):
        cache_key = 'scheme_{}'.format(self.pk)
        balance = cache.get(cache_key)

        if not balance:
            balance = self.get_midas_balance(user_consents=user_consents)
            if balance:
                balance.update({'updated_at': arrow.utcnow().timestamp, 'scheme_id': self.scheme.id})
                cache.set(cache_key, balance, settings.BALANCE_RENEW_PERIOD)

        if balance != self.balances and balance:
            self.balances = [{k: float(v) if isinstance(v, Decimal) else v for k, v in balance.items()}]
            self.save()

        return balance

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
    def action_status(self):
        if self.status in self.USER_ACTION_REQUIRED:
            return 'USER_ACTION_REQUIRED'
        elif self.status in self.SYSTEM_ACTION_REQUIRED:
            return 'SYSTEM_ACTION_REQUIRED'
        elif self.status == self.ACTIVE:
            return 'ACTIVE'
        elif self.status == self.WALLET_ONLY:
            return 'WALLET_ONLY'
        elif self.status == self.PENDING:
            return 'PENDING'

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

    ADD_FIELD = 0
    AUTH_FIELD = 1
    ENROL_FIELD = 2

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

    FIELD_TYPE_CHOICES = (
        (ADD_FIELD, 'add'),
        (AUTH_FIELD, 'auth'),
        (ENROL_FIELD, 'enrol'),
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
    field_type = models.IntegerField(choices=FIELD_TYPE_CHOICES, null=True, blank=True)

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

    def __str__(self):
        return self.value

    class Meta:
        ordering = ['value']


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
        encrypted_answer = AESCipher(settings.LOCAL_AES_KEY.encode()).encrypt(instance.answer).decode("utf-8")
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
