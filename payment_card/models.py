from django.db import models
from bulk_update.manager import BulkUpdateManager


class Issuer(models.Model):
    name = models.CharField(max_length=200)
    image = models.ImageField(upload_to="issuers")

    def __str__(self):
        return self.name


class PaymentCard(models.Model):
    VISA = 'visa'
    MATERCARD = 'mastercard'
    AMEX = 'amex'
    SYSTEMS = (
        (VISA, 'Visa'),
        (MATERCARD, 'Master Card'),
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


class ActiveManager(models.Manager):
    def get_queryset(self):
            return super(ActiveManager, self).get_queryset().exclude(status=PaymentCardAccount.DELETED)


class PaymentCardAccount(models.Model):
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
    payment_card = models.ForeignKey(PaymentCard)
    name_on_card = models.CharField(max_length=150)
    start_month = models.IntegerField(null=True)
    start_year = models.IntegerField(null=True)
    expiry_month = models.IntegerField()
    expiry_year = models.IntegerField()
    pan = models.CharField(max_length=50)
    status = models.IntegerField(default=PENDING, choices=STATUSES)
    order = models.IntegerField(default=0)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    postcode = models.CharField(max_length=20, blank=True, null=True)
    security_code = models.CharField(max_length=6)
    issuer = models.ForeignKey(Issuer)

    objects = BulkUpdateManager()
    active_objects = ActiveManager()

    def __str__(self):
        return self.pan
