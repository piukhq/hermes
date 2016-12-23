import sre_constants
from django.conf import settings
from django.db import models
from django.db.models import F
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils import timezone
from scheme.credentials import CREDENTIAL_TYPES, ENCRYPTED_CREDENTIALS, BARCODE, CARD_NUMBER
from bulk_update.manager import BulkUpdateManager
from scheme.encyption import AESCipher
from colorful.fields import RGBColorField
import json
import requests
import uuid
import re
import socket


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


class Scheme(models.Model):
    TIERS = (
        (1, 'Bink'),
        (2, 'Show'),
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
    company_url = models.URLField(blank=True, null=True)
    forgotten_password_url = models.URLField(max_length=500, blank=True, null=True)
    join_url = models.URLField(blank=True, null=True)
    join_t_and_c = models.TextField(blank=True, verbose_name="Join terms & conditions")
    link_account_text = models.TextField(blank=True, null=True)

    tier = models.IntegerField(choices=TIERS)

    ios_scheme = models.CharField(max_length=255, blank=True, null=True, verbose_name='iOS scheme')
    itunes_url = models.URLField(blank=True, null=True, verbose_name='iTunes URL')
    android_app_id = models.CharField(max_length=255, blank=True, null=True, verbose_name='Android app ID')
    play_store_url = models.URLField(blank=True, null=True, verbose_name='Play store URL')

    barcode_type = models.IntegerField(choices=BARCODE_TYPES, blank=True, null=True)
    scan_message = models.CharField(max_length=100)
    has_transactions = models.BooleanField(default=False)
    has_points = models.BooleanField(default=False)

    max_points_value_length = models.IntegerField(choices=MAX_POINTS_VALUE_LENGTHS, default=4,
                                                  help_text='The maximum number of digits the points value will reach. '
                                                            'This cannot be higher than four, because any arbitrarily '
                                                            'large number can be compressed down to four digits.')
    point_name = models.CharField(max_length=MAX_POINTS_VALUE_LENGTH - 1, default='points', null=True, blank=True,
                                  help_text='This field must have a length that, when added to the value of the above '
                                            'field, is less than or equal to {}.'.format(MAX_POINTS_VALUE_LENGTH - 1))

    identifier = models.CharField(max_length=30, null=True, blank=True, help_text="Regex identifier for barcode")
    colour = RGBColorField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    category = models.ForeignKey(Category)

    card_number_regex = models.CharField(max_length=100, null=True, blank=True,
                                         help_text="Regex to map barcode to card number")
    barcode_regex = models.CharField(max_length=100, null=True, blank=True,
                                     help_text="Regex to map card number to barcode")
    card_number_prefix = models.CharField(max_length=100, null=True, blank=True,
                                          help_text="Prefix to from barcode -> card number mapping")
    barcode_prefix = models.CharField(max_length=100, null=True, blank=True,
                                      help_text="Prefix to from card number -> barcode mapping")
    all_objects = models.Manager()
    objects = ActiveSchemeManager()

    @property
    def manual_question(self):
        return self.questions.filter(manual_question=True).first()

    @property
    def scan_question(self):
        return self.questions.filter(scan_question=True).first()

    @property
    def link_questions(self):
        return self.questions.exclude(scan_question=True).exclude(manual_question=True)

    def __str__(self):
        return self.name


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
        return super().get_queryset().filter(start_date__lt=timezone.now(),
                                             end_date__gte=timezone.now()).exclude(status=Image.DRAFT)


class Image(models.Model):
    DRAFT = 0
    PUBLISHED = 1

    STATUSES = (
        (DRAFT, 'draft'),
        (PUBLISHED, 'published'),
    )

    TYPES = (
        (0, 'hero'),
        (1, 'banner'),
        (2, 'offers'),
        (3, 'icon'),
        (4, 'asset'),
        (5, 'reference'),
        (6, 'personal offers'),
    )

    image_type_code = models.IntegerField(choices=TYPES)
    size_code = models.CharField(max_length=30, blank=True, null=True)
    image = models.ImageField(upload_to="schemes")
    strap_line = models.CharField(max_length=50, blank=True, null=True)
    description = models.CharField(max_length=300, blank=True, null=True)
    url = models.URLField(blank=True, null=True)
    call_to_action = models.CharField(max_length=150)
    order = models.IntegerField()
    status = models.IntegerField(default=DRAFT, choices=STATUSES)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField(blank=True, null=True)
    created = models.DateTimeField(default=timezone.now)

    objects = ActiveSchemeImageManager()
    all_objects = models.Manager()

    def __str__(self):
        return self.description

    class Meta:
        abstract = True


class SchemeImage(Image):
    scheme = models.ForeignKey('scheme.Scheme', related_name='images')


class ActiveSchemeIgnoreQuestionManager(BulkUpdateManager):

    def get_queryset(self):
        return super(ActiveSchemeIgnoreQuestionManager, self).get_queryset().exclude(is_deleted=True).\
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
    UNKNOWN_ERROR = 520
    MIDAS_UNREACHEABLE = 9
    AGENT_NOT_FOUND = 404
    WALLET_ONLY = 10
    PASSWORD_EXPIRED = 533
    JOIN = 900

    STATUSES = (
        (PENDING, 'Pending'),
        (ACTIVE, 'Active'),
        (INVALID_CREDENTIALS, 'Invalid credentials'),
        (INVALID_MFA, 'Invalid mfa'),
        (END_SITE_DOWN, 'End site down'),
        (IP_BLOCKED, 'IP blocked'),
        (TRIPPED_CAPTCHA, 'Tripped captcha'),
        (INCOMPLETE, 'Please check your scheme account login details.'),
        (LOCKED_BY_ENDSITE, 'Account locked on end site'),
        (RETRY_LIMIT_REACHED, 'Cannot connect, too many retries'),
        (UNKNOWN_ERROR, 'An unknown error has occurred'),
        (MIDAS_UNREACHEABLE, 'Midas unavailable'),
        (WALLET_ONLY, 'Wallet only card'),
        (AGENT_NOT_FOUND, 'Agent does not exist on midas'),
        (PASSWORD_EXPIRED, 'Password expired'),
        (JOIN, 'Join'),
    )
    USER_ACTION_REQUIRED = [INVALID_CREDENTIALS, INVALID_MFA, INCOMPLETE, LOCKED_BY_ENDSITE]
    SYSTEM_ACTION_REQUIRED = [END_SITE_DOWN, RETRY_LIMIT_REACHED, UNKNOWN_ERROR, MIDAS_UNREACHEABLE,
                              IP_BLOCKED, TRIPPED_CAPTCHA]

    user = models.ForeignKey('user.CustomUser')
    scheme = models.ForeignKey('scheme.Scheme')
    status = models.IntegerField(default=PENDING, choices=STATUSES)
    order = models.IntegerField()
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)

    all_objects = models.Manager()
    objects = ActiveSchemeIgnoreQuestionManager()

    @property
    def status_name(self):
        return dict(self.STATUSES).get(self.status)

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
        required_credentials = {question.type for question in self.scheme.questions.all()}
        manual_question = self.scheme.manual_question
        scan_question = self.scheme.scan_question

        if scan_question and manual_question and scan_question != manual_question:
            if scan_question.type in credential_types:
                required_credentials.remove(manual_question.type)
            if required_credentials and manual_question.type in credential_types:
                required_credentials.remove(scan_question.type)

        return required_credentials.difference(set(credential_types))

    def credentials(self):
        credentials = self._collect_credentials()
        if self.missing_credentials(credentials.keys()):
            self.status = SchemeAccount.INCOMPLETE
            self.save()
            return None
        serialized_credentials = json.dumps(credentials)
        return AESCipher(settings.AES_KEY.encode()).encrypt(serialized_credentials).decode('utf-8')

    def get_midas_balance(self):
        points = None
        try:
            credentials = self.credentials()
            if not credentials:
                return points
            parameters = {'scheme_account_id': self.id, 'user_id': self.user.id, 'credentials': credentials}
            headers = {"transaction": str(uuid.uuid1()), "User-agent": 'Hermes on {0}'.format(socket.gethostname())}
            response = requests.get('{}/{}/balance'.format(settings.MIDAS_URL, self.scheme.slug),
                                    params=parameters, headers=headers)
            self.status = response.status_code
            if response.status_code == 200:
                self.status = SchemeAccount.ACTIVE
                points = response.json()
                points['balance'] = points.get('balance')  # serializers.DecimalField does not allow blank fields
                points['is_stale'] = False
        except ConnectionError:
            self.status = SchemeAccount.MIDAS_UNREACHEABLE
        self.save()
        return points

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

    @property
    def images(self):
        qualifiers = SchemeAccountImage.objects.filter(scheme=self.scheme,
                                                       scheme_accounts__id=self.id,
                                                       scheme_image__isnull=False)
        images = qualifiers.annotate(image_type_code=F('scheme_image__image_type_code'),
                                     image_size_code=F('scheme_image__size_code'),
                                     image=F('scheme_image__image'),
                                     strap_line=F('scheme_image__strap_line'),
                                     image_description=F('scheme_image__description'),
                                     url=F('scheme_image__url'),
                                     call_to_action=F('scheme_image__call_to_action'),
                                     order=F('scheme_image__order'))\
            .values('image_type_code',
                    'image_size_code',
                    'image',
                    'strap_line',
                    'image_description',
                    'url',
                    'call_to_action',
                    'order',
                    'status',
                    'start_date',
                    'end_date',
                    'created')

        return images

    def __str__(self):
        return "{0} - {1}".format(self.user.email, self.scheme.name)

    class Meta:
        ordering = ['order', '-created']


class SchemeCredentialQuestion(models.Model):
    scheme = models.ForeignKey('Scheme', related_name='questions', on_delete=models.PROTECT)
    order = models.IntegerField(default=0)
    type = models.CharField(max_length=250, choices=CREDENTIAL_TYPES)
    label = models.CharField(max_length=250)
    third_party_identifier = models.BooleanField(default=False)

    manual_question = models.BooleanField(default=False)
    scan_question = models.BooleanField(default=False)

    class Meta:
        ordering = ['order']
        unique_together = ("scheme", "type")

    def __str__(self):
        return self.type


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


class SchemeAccountImage(Image):
    scheme = models.ForeignKey('scheme.Scheme', null=True, blank=True)
    scheme_accounts = models.ManyToManyField('scheme.SchemeAccount', related_name='scheme_accounts_set')

    def __str__(self):
        return self.description


@receiver(pre_save, sender=SchemeAccountCredentialAnswer)
def encryption_handler(sender, instance, **kwargs):
    if instance.question.type in ENCRYPTED_CREDENTIALS:
        encrypted_answer = AESCipher(settings.LOCAL_AES_KEY.encode()).encrypt(instance.answer).decode("utf-8")
        instance.answer = encrypted_answer
