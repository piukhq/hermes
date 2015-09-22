from django.db import models
from django.conf import settings

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
    forgotten_password_url = models.URLField()
    tier = models.IntegerField(choices=TIERS)
    barcode_type = models.IntegerField()
    scan_message = models.CharField(max_length=100)
    is_barcode = models.BooleanField()
    identifier = models.CharField(max_length=30)
    point_name = models.CharField(max_length=50, default='points')
    point_conversion_rate = models.DecimalField(max_digits=20, decimal_places=6)
    input_label = models.CharField(max_length=150)  # CARD PREFIX
    is_active = models.BooleanField(default=True)
    category = models.ForeignKey(Category)

    def __str__(self):
        return self.name


class SchemeImage(models.Model):
    DRAFT = 0
    PUBLISHED = 1

    STATUSES = (
        (DRAFT, 'draft'),
        (PUBLISHED, 'published'),
    )
    scheme = models.ForeignKey('scheme.Scheme')
    image_type_code = models.IntegerField()
    size_code = models.CharField(max_length=30)
    image_path = models.CharField(max_length=300)
    strap_line = models.CharField(max_length=50)
    description = models.CharField(max_length=300)
    url = models.URLField()
    call_to_action = models.CharField(max_length=50)
    order = models.IntegerField()
    status = models.IntegerField(default=DRAFT, choices=STATUSES)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    created = models.DateTimeField(auto_now_add=True)


class ActiveManager(models.Manager):
    def get_queryset(self):
            return super(ActiveManager, self).get_queryset().exclude(status=SchemeAccount.DELETED)


class AESModel(object):
    """
    Mixin to aes encrypt the specified 'aes field'
    """
    __aes_field__ = None
    _original_password = None

    def __init__(self, *args, **kwargs):
        super(AESModel, self).__init__(*args, **kwargs)
        self._original_password = getattr(self, self.__aes_field__)

    def save(self, *args, **kwargs):
        """Ensure our password is always encrypted"""
        new_password = getattr(self, self.__aes_field__)
        if new_password != self._original_password or not self.pk:
            aes_cipher = AESCipher(key=settings.AES_KEY.encode('utf-8'))
            setattr(self, self.__aes_field__, aes_cipher.encrypt(new_password).decode('utf-8'))
        super(AESModel, self).save(*args, **kwargs)
        self._original_password = new_password


class SchemeAccount(AESModel, models.Model):
    __aes_field__ = "password"

    PENDING = 0
    ACTIVE = 1
    INVALID_CREDENTIALS = 2
    END_SITE_DOWN = 3
    DELETED = 4

    STATUSES = (
        (PENDING, 'pending'),
        (ACTIVE, 'active'),
        (INVALID_CREDENTIALS, 'invalid credentials'),
        (END_SITE_DOWN, 'end site down'),
        (DELETED, 'deleted'),
    )

    user = models.ForeignKey('user.CustomUser')
    scheme = models.ForeignKey('scheme.Scheme')
    username = models.CharField(max_length=150)
    card_number = models.CharField(max_length=50)
    membership_number = models.CharField(max_length=50, blank=True, null=True)
    password = models.TextField()
    status = models.IntegerField(default=PENDING, choices=STATUSES)
    order = models.IntegerField(default=0)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    objects = models.Manager()
    active_objects = ActiveManager()

    def __str__(self):
        return "{0} - {1}".format(self.user.email, self.scheme.name)


class SchemeAccountSecurityQuestion(AESModel, models.Model):
    __aes_field__ = "answer"

    scheme_account = models.ForeignKey(SchemeAccount)
    question = models.CharField(max_length=250)
    answer = models.CharField(max_length=250)
