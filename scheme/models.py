from django.conf import settings
from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils import timezone
from scheme.credentials import CREDENTIAL_TYPES, ENCRYPTED_CREDENTIALS
from bulk_update.manager import BulkUpdateManager
from scheme.encyption import AESCipher


class Category(models.Model):
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name


class ActiveSchemeManager(models.Manager):
    def get_queryset(self):
        return super(ActiveSchemeManager, self).get_queryset().exclude(primary_question__isnull=True, is_active=True)


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
    point_conversion_rate = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    primary_question = models.ForeignKey('SchemeCredentialQuestion', null=True, blank=True,
                                         related_name='primary_question')
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
    image_type_code = models.IntegerField()
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
            return super(ActiveManager, self).get_queryset().exclude(status=SchemeAccount.DELETED)


class SchemeAccount(models.Model):
    PENDING = 0
    ACTIVE = 1
    INVALID_CREDENTIALS = 403
    INVALID_MFA = 432
    END_SITE_DOWN = 530
    DELETED = 4
    INCOMPLETE = 5
    LOCKED_BY_ENDSITE = 434
    RETRY_LIMIT_REACHED = 429
    UNKNOWN_ERROR = 520
    MIDAS_UNREACHEABLE = 9
    WALLET_ONLY = 10

    STATUSES = (
        (PENDING, 'pending'),
        (ACTIVE, 'active'),
        (INVALID_CREDENTIALS, 'invalid credentials'),
        (INVALID_MFA, 'invalid_mfa'),
        (END_SITE_DOWN, 'end site down'),
        (DELETED, 'deleted'),
        (INCOMPLETE, 'incomplete'),
        (LOCKED_BY_ENDSITE, 'account locked on end site'),
        (RETRY_LIMIT_REACHED, 'Cannot connect, too many retries'),
        (UNKNOWN_ERROR, 'An unknown error has occurred'),
        (MIDAS_UNREACHEABLE, 'Midas unavailable'),
        (WALLET_ONLY, 'This is a wallet only card')
    )

    user = models.ForeignKey('user.CustomUser')
    scheme = models.ForeignKey('scheme.Scheme')
    status = models.IntegerField(default=PENDING, choices=STATUSES)
    order = models.IntegerField(default=0)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    objects = BulkUpdateManager()
    active_objects = ActiveManager()

    def credentials(self):
        challenges_with_responses = {}
        security_questions = SchemeCredentialQuestion.objects.filter(scheme=self.scheme)
        if security_questions:
            for security_question in security_questions:
                answer = SchemeAccountCredentialAnswer.objects.get(scheme_account=self,
                                                                   type=security_question.type)
                challenges_with_responses[security_question.type] = answer.answer
        return challenges_with_responses

    @property
    def primary_answer(self):
        return self.schemeaccountcredentialanswer_set.get(type=self.scheme.primary_question.type)

    @property
    def action_status(self):
        if self.status in [self.INVALID_CREDENTIALS,
                           self.INVALID_MFA,
                           self.INCOMPLETE]:
            return 'USER_ACTION_REQUIRED'
        elif self.status in [self.END_SITE_DOWN,
                             self.LOCKED_BY_ENDSITE,
                             self.RETRY_LIMIT_REACHED,
                             self.UNKNOWN_ERROR,
                             self.MIDAS_UNREACHEABLE]:
            return 'SYSTEM_ACTION_REQUIRED'
        elif self.status == self.ACTIVE:
            return 'ACTIVE'
        elif self.status == self.DELETED:
            return 'DELETED'
        elif self.status == self.WALLET_ONLY:
            return 'WALLET_ONLY'

    def __str__(self):
        return "{0} - {1}".format(self.user.email, self.scheme.name)

    class Meta:
        ordering = ['order']


class SchemeCredentialQuestion(models.Model):
    scheme = models.ForeignKey('Scheme', related_name='questions')
    order = models.IntegerField(default=0)
    type = models.CharField(max_length=250, choices=CREDENTIAL_TYPES)
    label = models.CharField(max_length=250)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.type


class SchemeAccountCredentialAnswer(models.Model):
    scheme_account = models.ForeignKey(SchemeAccount)
    type = models.CharField(max_length=250, choices=CREDENTIAL_TYPES)
    answer = models.CharField(max_length=250)

    def __str__(self):
        return self.answer


@receiver(pre_save, sender=SchemeAccountCredentialAnswer)
def encryption_handler(sender, instance, **kwargs):
    if instance.type in ENCRYPTED_CREDENTIALS:
        encrypted_answer = AESCipher(settings.LOCAL_AES_KEY.encode()).encrypt(instance.answer).decode("utf-8")
        instance.answer = encrypted_answer
