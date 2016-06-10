from bulk_update.helper import bulk_update
from django.db import models
from django.db.models import F
from django.utils import timezone


class Issuer(models.Model):
    name = models.CharField(max_length=200)
    image = models.ImageField(upload_to="issuers")

    def __str__(self):
        return self.name


class ActivePaymentCardImageManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset()\
            .filter(start_date__lt=timezone.now(), end_date__gte=timezone.now()).exclude(status=0)


IMAGE_TYPES = (
    (0, 'hero'),
    (1, 'banner'),
    (2, 'offers'),
    (3, 'icon'),
    (4, 'asset'),
    (5, 'reference'),
    (6, 'personal offers'),
)


class PaymentCardImage(models.Model):
    DRAFT = 0
    PUBLISHED = 1

    STATUSES = (
        (DRAFT, 'draft'),
        (PUBLISHED, 'published'),
    )

    payment_card = models.ForeignKey('payment_card.PaymentCard', related_name='images')
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
    objects = ActivePaymentCardImageManager()


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
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    url = models.URLField()
    image = models.ImageField(upload_to="payment_cards")
    scan_message = models.CharField(max_length=100)
    input_label = models.CharField(max_length=150)  # CARD PREFIX
    is_active = models.BooleanField(default=True)
    system = models.CharField(max_length=40, choices=SYSTEMS)
    type = models.CharField(max_length=40, choices=TYPES)

    def __str__(self):
        return self.name


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
    start_month = models.IntegerField(null=True)
    start_year = models.IntegerField(null=True)
    expiry_month = models.IntegerField()
    expiry_year = models.IntegerField()
    currency_code = models.CharField(max_length=3)
    country = models.CharField(max_length=40)
    token = models.CharField(max_length=255, db_index=True)
    pan_start = models.CharField(max_length=6)
    pan_end = models.CharField(max_length=6)
    status = models.IntegerField(default=PENDING, choices=STATUSES)
    order = models.IntegerField(default=0)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    issuer = models.ForeignKey(Issuer)
    is_deleted = models.BooleanField(default=False)

    objects = PaymentCardAccountManager()

    def __str__(self):
        return "{0}******{1}".format(self.pan_start, self.pan_end)

    @property
    def status_name(self):
        return dict(self.STATUSES).get(self.status)

    @property
    def images(self):
        qualifiers = PaymentCardAccountImageCriteria.objects.filter(payment_card=self.payment_card,
                                                                payment_card_accounts__id=self.id,
                                                                payment_image__isnull=False)
        images = qualifiers.annotate(image_type_code=F('payment_image__image_type_code'),
                                     image_size_code=F('payment_image__size_code'),
                                     image=F('payment_image__image'),
                                     strap_line=F('payment_image__strap_line'),
                                     image_description=F('payment_image__description'),
                                     url=F('payment_image__url'),
                                     call_to_action=F('payment_image__call_to_action'),
                                     order=F('payment_image__order')) \
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


class PaymentCardAccountImage(models.Model):
    image_type_code = models.IntegerField(choices=IMAGE_TYPES)
    size_code = models.CharField(max_length=30, null=True, blank=True)
    image = models.ImageField(upload_to="schemes")
    strap_line = models.CharField(max_length=50, null=True, blank=True)
    description = models.CharField(max_length=300, null=True, blank=True)
    url = models.URLField(null=True, blank=True)
    call_to_action = models.CharField(max_length=150)
    order = models.IntegerField()
    created = models.DateTimeField(default=timezone.now)


class PaymentCardAccountImageCriteria(models.Model):
    DRAFT = 0
    PUBLISHED = 1

    STATUSES = (
        (DRAFT, 'draft'),
        (PUBLISHED, 'published'),
    )

    payment_card = models.ForeignKey('payment_card.PaymentCard', null=True, blank=True)
    payment_card_accounts = models.ManyToManyField('payment_card.PaymentCardAccount',
                                                   related_name='payment_card_accounts_set')

    description = models.CharField(max_length=300, null=True, blank=True)
    status = models.IntegerField(default=DRAFT, choices=STATUSES)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField(blank=True, null=True)
    created = models.DateTimeField(default=timezone.now)

    payment_image = models.ForeignKey('payment_card.PaymentCardAccountImage', null=True, blank=True)
