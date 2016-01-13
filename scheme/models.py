import socket
from django.conf import settings
from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils import timezone
from scheme.credentials import CREDENTIAL_TYPES, ENCRYPTED_CREDENTIALS
from bulk_update.manager import BulkUpdateManager
from scheme.encyption import AESCipher
from colorful.fields import RGBColorField
import json
import requests
import uuid


class Category(models.Model):
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name


class ActiveSchemeManager(models.Manager):
    def get_queryset(self):
        return super(ActiveSchemeManager, self).get_queryset().exclude(
            manual_question__isnull=True).exclude(is_active=False)


class Scheme(models.Model):
    TIERS = (
        (1, 'Tier 1'),
        (2, 'Tier 2'),
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

    # this is the same slugs found in the active.py file in the midas repo
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    url = models.URLField()
    company = models.CharField(max_length=200)
    company_url = models.URLField(blank=True, null=True)
    forgotten_password_url = models.URLField(max_length=500)
    tier = models.IntegerField(choices=TIERS)
    barcode_type = models.IntegerField(choices=BARCODE_TYPES, blank=True, null=True)
    scan_message = models.CharField(max_length=100)
    has_transactions = models.BooleanField(default=False)
    has_points = models.BooleanField(default=False)
    identifier = models.CharField(max_length=30, null=True, blank=True, help_text="Regex identifier for barcode")
    point_name = models.CharField(max_length=50, default='points', null=True, blank=True)
    manual_question = models.ForeignKey('SchemeCredentialQuestion', null=True, blank=True,
                                        related_name='manual_question')
    # scan_question = models.ForeignKey('SchemeCredentialQuestion', null=True, blank=True,
    #                                   related_name='scan_question')
    colour = RGBColorField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    category = models.ForeignKey(Category)

    all_objects = models.Manager()
    objects = ActiveSchemeManager()

    @property
    def is_barcode(self):
        if self.barcode_type is not None:
            return True
        return False

    @property
    def challenges(self):
        return self.questions.all()

    def __str__(self):
        return self.name


class ActiveSchemeImageManager(models.Manager):
    def get_queryset(self):
        return super(ActiveSchemeImageManager, self).get_queryset()\
            .filter(start_date__lt=timezone.now, end_date__gte=timezone.now())\
            .exclude(status=0)


class SchemeImage(models.Model):
    DRAFT = 0
    PUBLISHED = 1

    STATUSES = (
        (DRAFT, 'draft'),
        (PUBLISHED, 'published'),
    )

    IMAGE_TYPES = (
        (0, 'hero'),
        (1, 'banner'),
        (2, 'offers'),
        (3, 'icon'),
        (4, 'asset'),
        (5, 'reference'),
    )

    scheme = models.ForeignKey('scheme.Scheme', related_name='images')
    image_type_code = models.IntegerField(choices=IMAGE_TYPES)
    size_code = models.CharField(max_length=30, null=True, blank=True)
    image = models.ImageField(upload_to="schemes")
    strap_line = models.CharField(max_length=50, null=True, blank=True)
    description = models.CharField(max_length=300, null=True, blank=True)
    url = models.URLField(null=True, blank=True)
    call_to_action = models.CharField(max_length=150)
    order = models.IntegerField()
    status = models.IntegerField(default=DRAFT, choices=STATUSES)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    created = models.DateTimeField(default=timezone.now)

    all_objects = models.Manager()
    objects = ActiveSchemeImageManager()


class ActiveManager(models.Manager):
    def get_queryset(self):
            return super(ActiveManager, self).get_queryset().exclude(is_deleted=True)


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
        (PASSWORD_EXPIRED, "Password expired")
    )
    USER_ACTION_REQUIRED = [INVALID_CREDENTIALS, INVALID_MFA, INCOMPLETE, LOCKED_BY_ENDSITE]
    SYSTEM_ACTION_REQUIRED = [END_SITE_DOWN, RETRY_LIMIT_REACHED, UNKNOWN_ERROR, MIDAS_UNREACHEABLE,
                              IP_BLOCKED, TRIPPED_CAPTCHA]

    user = models.ForeignKey('user.CustomUser')
    scheme = models.ForeignKey('scheme.Scheme')
    status = models.IntegerField(default=PENDING, choices=STATUSES)
    order = models.IntegerField(default=0)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)

    objects = BulkUpdateManager()
    active_objects = ActiveManager()

    @property
    def status_name(self):
        return dict(self.STATUSES).get(self.status)

    def _collect_credentials(self):
        credentials = {}
        for answer in self.schemeaccountcredentialanswer_set.all():
            if answer.question.type in ENCRYPTED_CREDENTIALS:
                credentials[answer.question.type] = AESCipher(settings.LOCAL_AES_KEY.encode()).decrypt(answer.answer)
            else:
                credentials[answer.question.type] = answer.answer
        return credentials

    def missing_credentials(self, credential_types):
        """
        Given a list of credential_types are they all that's required by the scheme
        """
        return {question.type for question in self.scheme.questions.all()}.difference(set(credential_types))

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
        return SchemeCredentialQuestion.objects.get(type=question_type, scheme=self.scheme)

    @property
    def manual_answer(self):
        return self.schemeaccountcredentialanswer_set.filter(question=self.scheme.manual_question).first()

    @property
    def manual_answer_id(self):
        manual_answer = self.manual_answer
        if manual_answer:
            return manual_answer.id
        return None

    @property
    def answers(self):
        return self.schemeaccountcredentialanswer_set.all()

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

    def __str__(self):
        return "{0} - {1}".format(self.user.email, self.scheme.name)

    class Meta:
        ordering = ['order', '-created']


class SchemeCredentialQuestion(models.Model):
    scheme = models.ForeignKey('Scheme', related_name='questions', on_delete=models.PROTECT)
    order = models.IntegerField(default=0)
    type = models.CharField(max_length=250, choices=CREDENTIAL_TYPES)
    label = models.CharField(max_length=250)

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


@receiver(pre_save, sender=SchemeAccountCredentialAnswer)
def encryption_handler(sender, instance, **kwargs):
    if instance.question.type in ENCRYPTED_CREDENTIALS:
        encrypted_answer = AESCipher(settings.LOCAL_AES_KEY.encode()).encrypt(instance.answer).decode("utf-8")
        instance.answer = encrypted_answer
