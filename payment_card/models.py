from django.db import models
from bulk_update.manager import BulkUpdateManager
from django.core.exceptions import ValidationError


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


def validate_pan_start(value):
    if len(str(value)) != 6:
        raise ValidationError('{0} is not of the correct length {1}'.format(value, 6))


def validate_pan_end(value):
    if len(str(value)) != 4:
        raise ValidationError('{0} is not of the correct length {1}'.format(value, 4))


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
    pan_start = models.CharField(validators=[validate_pan_start], max_length=6)
    pan_end = models.CharField(validators=[validate_pan_end], max_length=4)
    status = models.IntegerField(default=PENDING, choices=STATUSES)
    order = models.IntegerField(default=0)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    issuer = models.ForeignKey(Issuer)

    objects = BulkUpdateManager()

    def __str__(self):
        return "{0}******{1}".format(self.pan_start, self.pan_end)

    @property
    def status_name(self):
        return dict(self.STATUSES).get(self.status)
