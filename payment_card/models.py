from bulk_update.helper import bulk_update
from django.db import models
from django.db.models import F
from django.utils import timezone
import base64
import uuid


class Issuer(models.Model):
    name = models.CharField(max_length=200)
    image = models.ImageField(upload_to="issuers")

    def __str__(self):
        return self.name


class ActivePaymentCardImageManager(models.Manager):

    def get_queryset(self):
        return super().get_queryset().filter(
            start_date__lt=timezone.now(), end_date__gte=timezone.now()).exclude(status=Image.DRAFT)


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
    size_code = models.CharField(max_length=30, null=True, blank=True)
    image = models.ImageField(upload_to="schemes")
    strap_line = models.CharField(max_length=50, null=True, blank=True)
    description = models.CharField(max_length=300, null=True, blank=True)
    url = models.URLField(null=True, blank=True)
    call_to_action = models.CharField(max_length=150)
    order = models.IntegerField()
    status = models.IntegerField(default=DRAFT, choices=STATUSES)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField(blank=True, null=True)
    created = models.DateTimeField(default=timezone.now)

    objects = ActivePaymentCardImageManager()
    all_objects = models.Manager()

    def __str__(self):
        return self.description

    class Meta:
        abstract = True


class PaymentCardImage(Image):
    payment_card = models.ForeignKey('payment_card.PaymentCard', related_name='images')


class PaymentCard(models.Model):
    VISA = 'visa'
    MASTERCARD = 'mastercard'
    AMEX = 'amex'
    SYSTEMS = (
        (VISA, 'Visa'),
        (MASTERCARD, 'Master Card'),
        (AMEX, 'American Express‎'),
    )
    DEBIT = 'debit'
    CREDIT = 'credit'
    TYPES = (
        (DEBIT, 'Debit Card'),
        (CREDIT, 'Credit Card'),
    )

    class TokenMethod(object):
        COPY = 0
        LEN_24 = 1
        LEN_25 = 2

        CHOICES = (
            (COPY, 'Use PSP token'),
            (LEN_24, 'Generate length-24 token'),
            (LEN_25, 'Generate length-25 token'),
        )

        @classmethod
        def copy(cls, psp_token):
            return psp_token

        @classmethod
        def len24(cls, psp_token):
            return base64.b64encode(uuid.uuid4().bytes).decode('utf-8')

        @classmethod
        def len25(cls, psp_token):
            # calculate UPC check digit
            odds = sum(ord(c) for c in psp_token[::2]) * 3
            evens = sum(ord(c) for c in psp_token[1::2])
            check_digit = (odds + evens) % 10
            if check_digit != 0:
                check_digit = 10 - check_digit
            return '{}{}'.format(cls.len24(psp_token), check_digit)

        @classmethod
        def dispatch(cls, method, psp_token):
            return {cls.COPY:   cls.copy,
                    cls.LEN_24: cls.len24,
                    cls.LEN_25: cls.len25}[method](psp_token)

    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    url = models.URLField()
    scan_message = models.CharField(max_length=100)
    input_label = models.CharField(max_length=150)  # CARD PREFIX
    is_active = models.BooleanField(default=True)
    system = models.CharField(max_length=40, choices=SYSTEMS)
    type = models.CharField(max_length=40, choices=TYPES)
    token_method = models.IntegerField(default=TokenMethod.COPY, choices=TokenMethod.CHOICES)

    def __str__(self):
        return self.name

    @property
    def images(self):
        return PaymentCardImage.objects.filter(payment_card=self.id)


class PaymentCardAccountManager(models.Manager):

    def get_queryset(self):
        return super(PaymentCardAccountManager, self).get_queryset().exclude(is_deleted=True)

    def bulk_update(self, objs, update_fields=None, exclude_fields=None):
        bulk_update(objs, update_fields=update_fields,
                    exclude_fields=exclude_fields, using=self.db)


class PaymentCardAccount(models.Model):
    PENDING = 0
    ACTIVE = 1

    STATUSES = (
        (PENDING, 'pending'),
        (ACTIVE, 'active'),
    )

    user = models.ForeignKey('user.CustomUser')
    payment_card = models.ForeignKey(PaymentCard)
    name_on_card = models.CharField(max_length=150)
    start_month = models.IntegerField(null=True, blank=True)
    start_year = models.IntegerField(null=True, blank=True)
    expiry_month = models.IntegerField()
    expiry_year = models.IntegerField()
    currency_code = models.CharField(max_length=3)
    country = models.CharField(max_length=40)
    token = models.CharField(max_length=255, db_index=True)
    psp_token = models.CharField(max_length=255, verbose_name='PSP Token')
    pan_start = models.CharField(max_length=6)
    pan_end = models.CharField(max_length=4)
    status = models.IntegerField(default=PENDING, choices=STATUSES)
    order = models.IntegerField()
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    issuer = models.ForeignKey(Issuer)
    fingerprint = models.CharField(max_length=100)
    is_deleted = models.BooleanField(default=False)

    all_objects = models.Manager()
    objects = PaymentCardAccountManager()

    def __str__(self):
        return '({}) {} - {}'.format(
            self.user.email,
            self.payment_card.name,
            self.name_on_card
        )

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = PaymentCard.TokenMethod.dispatch(self.payment_card.token_method, self.psp_token)
        super().save(*args, **kwargs)

    @property
    def status_name(self):
        return dict(self.STATUSES).get(self.status)

    @property
    def images(self):
        qualifiers = PaymentCardAccountImage.objects.filter(payment_card=self.payment_card,
                                                            payment_card_accounts__id=self.id,
                                                            payment_card_image__isnull=False)
        images = qualifiers.annotate(image_type_code=F('payment_card_image__image_type_code'),
                                     image_size_code=F('payment_card_image__size_code'),
                                     image=F('payment_card_image__image'),
                                     strap_line=F('payment_card_image__strap_line'),
                                     image_description=F('payment_card_image__description'),
                                     url=F('payment_card_image__url'),
                                     call_to_action=F('payment_card_image__call_to_action'),
                                     order=F('payment_card_image__order')).values(
                                         'image_type_code',
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


class PaymentCardAccountImage(Image):
    payment_card = models.ForeignKey('payment_card.PaymentCard', null=True, blank=True)
    payment_card_accounts = models.ManyToManyField('payment_card.PaymentCardAccount',
                                                   related_name='payment_card_accounts_set',
                                                   blank=True)
