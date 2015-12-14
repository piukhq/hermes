from bulk_update.helper import bulk_update
from django.db import models


class Issuer(models.Model):
    name = models.CharField(max_length=200)
    image = models.ImageField(upload_to="issuers")

    def __str__(self):
        return self.name


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
    token = models.CharField(max_length=255)
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
