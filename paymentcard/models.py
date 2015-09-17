from django.db import models


class Issuer(models.Model):
    name = models.CharField(max_length=200)
    image = models.ImageField()


class PaymentCard(models.Model):
    SYSTEMS = (
        ('visa', 'Visa'),
        ('mastercard', 'Master Card'),
        ('amex', 'American Express‎'),
    )
    TYPES = (
        ('debit', 'Debit Card'),
        ('credit', 'Credit Card'),
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    url = models.URLField()
    image = models.ImageField(null=True)
    scan_message = models.CharField(max_length=100)
    input_label = models.CharField(max_length=150)  # CARD PREFIX
    is_active = models.BooleanField(default=True)
    system = models.CharField(max_length=40, choices=SYSTEMS)
    type = models.CharField(max_length=40, choices=TYPES)


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
