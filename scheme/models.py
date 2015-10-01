from django.db import models
from django.conf import settings
from django.utils.text import slugify
from django.utils import timezone
from scheme.credentials import CREDENTIAL_TYPES

from scheme.encyption import AESCipher


class Category(models.Model):
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name


class Scheme(models.Model):
    TIERS = (
        (1, 'Tier 1'),
        (2, 'Tier 2'),
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    url = models.URLField()
    company = models.CharField(max_length=200)
    company_url = models.URLField()
    forgotten_password_url = models.URLField(max_length=500)
    tier = models.IntegerField(choices=TIERS)
    barcode_type = models.IntegerField()
    scan_message = models.CharField(max_length=100)
    is_barcode = models.BooleanField()
    identifier = models.CharField(max_length=30)
    point_name = models.CharField(max_length=50, default='points')
    point_conversion_rate = models.DecimalField(max_digits=20, decimal_places=6)
    primary_question = models.ForeignKey('SchemeCredentialQuestion', null=True, blank=True,
                                         related_name='primary_question')
    is_active = models.BooleanField(default=True)
    category = models.ForeignKey(Category)

    @property
    def challenges(self):
        return self.questions.all()

    def __str__(self):
        return self.name


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

    scheme = models.ForeignKey('scheme.Scheme')
    image_type_code = models.IntegerField()
    size_code = models.CharField(max_length=30)
    image = models.ImageField(upload_to="schemes")
    strap_line = models.CharField(max_length=50)
    description = models.CharField(max_length=300)
    url = models.URLField()
    call_to_action = models.CharField(max_length=150)
    order = models.IntegerField()
    status = models.IntegerField(default=DRAFT, choices=STATUSES)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    created = models.DateTimeField(default=timezone.now)


class ActiveManager(models.Manager):
    def get_queryset(self):
            return super(ActiveManager, self).get_queryset().exclude(status=SchemeAccount.DELETED)


class SchemeAccount(models.Model):
    PENDING = 0
    ACTIVE = 1
    INVALID_CREDENTIALS = 2
    END_SITE_DOWN = 3
    DELETED = 4
    INCOMPLETE = 5
    LOCKED_BY_ENDSITE = 6
    RETRY_LIMIT_REACHED = 7
    UNKNOWN_ERROR = 8

    STATUSES = (
        (PENDING, 'pending'),
        (ACTIVE, 'active'),
        (INVALID_CREDENTIALS, 'invalid credentials'),
        (END_SITE_DOWN, 'end site down'),
        (DELETED, 'deleted'),
        (INCOMPLETE, 'incomplete'),
        (LOCKED_BY_ENDSITE, 'account locked on end site'),
        (RETRY_LIMIT_REACHED, 'Cannot connect, too many retries'),
        (UNKNOWN_ERROR, 'An unknown error has occurred'),
    )

    user = models.ForeignKey('user.CustomUser')
    scheme = models.ForeignKey('scheme.Scheme')
    status = models.IntegerField(default=PENDING, choices=STATUSES)
    order = models.IntegerField(default=0)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    objects = models.Manager()
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

    def __str__(self):
        return "{0} - {1}".format(self.user.email, self.scheme.name)

    class Meta:
        ordering = ['-order']


class SchemeCredentialQuestion(models.Model):
    scheme = models.ForeignKey('Scheme', related_name='questions')
    order = models.IntegerField(default=0)
    type = models.CharField(max_length=250, choices=CREDENTIAL_TYPES)
    label = models.CharField(max_length=250)

    class Meta:
        ordering = ['-order']


class SchemeAccountCredentialAnswer(models.Model):
    scheme_account = models.ForeignKey(SchemeAccount)
    type = models.CharField(max_length=250, choices=CREDENTIAL_TYPES)
    answer = models.CharField(max_length=250)
