import base64
import uuid
from enum import IntEnum
from functools import lru_cache

from django.contrib.postgres.fields import JSONField
from django.db import models
from django.db.models import F, Q, signals
from django.dispatch import receiver
from django.utils import timezone

from common.models import Image
from scheme.models import SchemeAccount


class Issuer(models.Model):
    name = models.CharField(max_length=200)
    image = models.ImageField(upload_to="issuers")

    def __str__(self):
        return self.name

    @classmethod
    @lru_cache(maxsize=1)
    def get_barclays_issuer(cls):
        return cls.objects.get(name='Barclays')


def clear_issuer_lru_cache(sender, **kwargs):
    sender.get_barclays_issuer.cache_clear()


signals.post_save.connect(clear_issuer_lru_cache, sender=Issuer)
signals.post_delete.connect(clear_issuer_lru_cache, sender=Issuer)


class ActivePaymentCardImageManager(models.Manager):

    def get_queryset(self):
        return super().get_queryset().filter(
            start_date__lt=timezone.now()).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=timezone.now())).exclude(status=Image.DRAFT)


class PaymentCardImage(Image):
    objects = ActivePaymentCardImageManager()
    payment_card = models.ForeignKey('payment_card.PaymentCard', related_name='images', on_delete=models.CASCADE)


def _update_payment_card_images(instance: PaymentCardImage) -> None:
    payment_card = instance.payment_card
    query = {
        'payment_card': payment_card,
        'status': Image.PUBLISHED,
        'image_type_code__in': [Image.HERO, Image.ICON, Image.ALT_HERO]
    }
    formatted_images = {}
    # using PaymentCardImage.all_objects instead of payment_card.images to bypass ActivePaymentCardImageManager
    for img in PaymentCardImage.all_objects.filter(**query).all():
        if img.image_type_code not in formatted_images:
            formatted_images[img.image_type_code] = {}

        formatted_images[img.image_type_code][img.id] = img.ubiquity_format()

    payment_card.formatted_images = formatted_images
    payment_card.save(update_fields=['formatted_images'])


@receiver(signals.post_save, sender=PaymentCardImage)
def update_payment_card_images_on_save(sender, instance, created, **kwargs):
    _update_payment_card_images(instance)


@receiver(signals.post_delete, sender=PaymentCardImage)
def update_payment_card_images_on_delete(sender, instance, **kwargs):
    _update_payment_card_images(instance)


class PaymentCardAccountImage(Image):
    objects = ActivePaymentCardImageManager()
    payment_card = models.ForeignKey('payment_card.PaymentCard', null=True, blank=True, on_delete=models.SET_NULL)
    payment_card_accounts = models.ManyToManyField('payment_card.PaymentCardAccount',
                                                   related_name='images',
                                                   blank=True)


@receiver(signals.m2m_changed, sender=PaymentCardAccountImage.payment_card_accounts.through)
def update_payment_card_account_images_on_save(sender, instance, action, **kwargs):
    wrong_image_type = instance.image_type_code not in [Image.HERO, Image.ICON, Image.ALT_HERO]
    wrong_action = action != "post_add"
    image_is_draft = instance.status == Image.DRAFT

    if wrong_action or image_is_draft or wrong_image_type:
        return

    formatted_image = instance.ubiquity_format()
    for payment_card_account in instance.payment_card_accounts.all():
        images_to_update = payment_card_account.formatted_images.get(instance.image_type_code, {})
        images_to_update[instance.id] = formatted_image
        payment_card_account.formatted_images[instance.image_type_code] = images_to_update
        payment_card_account.save(update_fields=['formatted_images'])


@receiver(signals.pre_delete, sender=PaymentCardAccountImage)
def update_payment_card_account_images_on_delete(sender, instance, **kwargs):
    if instance.image_type_code not in [Image.HERO, Image.ICON, Image.ALT_HERO]:
        return

    for payment_card_account in instance.payment_card_accounts.all():
        try:
            del payment_card_account.formatted_images[str(instance.image_type_code)][str(instance.id)]
        except (KeyError, TypeError):
            pass
        else:
            payment_card_account.save(update_fields=['formatted_images'])


class PaymentCard(models.Model):
    VISA = 'visa'
    MASTERCARD = 'mastercard'
    AMEX = 'amex'
    SYSTEMS = (
        (VISA, 'Visa'),
        (MASTERCARD, 'Mastercard'),
        (AMEX, 'American Express'),
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
            return {cls.COPY: cls.copy,
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
    formatted_images = JSONField(default=dict, blank=True)

    def __str__(self):
        return self.name

    @property
    def system_name(self):
        return dict(self.SYSTEMS).get(self.system)

    @property
    def images(self):
        return PaymentCardImage.objects.filter(payment_card=self.id)

    @classmethod
    @lru_cache(maxsize=32)
    def get_by_slug(cls, slug: str) -> int:
        return cls.objects.get(slug=slug)


def clear_payment_card_lru_cache(sender, **kwargs):
    sender.get_by_slug.cache_clear()


signals.post_save.connect(clear_payment_card_lru_cache, sender=PaymentCard)
signals.post_delete.connect(clear_payment_card_lru_cache, sender=PaymentCard)


class PaymentCardAccountManager(models.Manager):

    def get_queryset(self):
        return super(PaymentCardAccountManager, self).get_queryset().exclude(is_deleted=True)

    # TODO check to see why we have this code here and uncomment if needed
    # def bulk_update(self, objs, update_fields=None, exclude_fields=None):
    #     bulk_update(objs, update_fields=update_fields,
    #                 exclude_fields=exclude_fields, using=self.db)


class PaymentCardAccount(models.Model):
    PENDING = 0
    ACTIVE = 1
    DUPLICATE_CARD = 2
    NOT_PROVIDER_CARD = 3
    INVALID_CARD_DETAILS = 4
    PROVIDER_SERVER_DOWN = 5
    UNKNOWN = 6

    STATUSES = (
        (PENDING, 'pending'),
        (ACTIVE, 'active'),
        (DUPLICATE_CARD, 'duplicate card'),
        (NOT_PROVIDER_CARD, 'not provider card'),
        (INVALID_CARD_DETAILS, 'invalid card details'),
        (PROVIDER_SERVER_DOWN, 'provider server down'),
        (UNKNOWN, 'unknown')
    )

    user_set = models.ManyToManyField('user.CustomUser', through='ubiquity.PaymentCardAccountEntry',
                                      related_name='payment_card_account_set')
    scheme_account_set = models.ManyToManyField('scheme.SchemeAccount', through='ubiquity.PaymentCardSchemeEntry',
                                                related_name='payment_card_account_set')
    payment_card = models.ForeignKey(PaymentCard, models.PROTECT)
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
    issuer = models.ForeignKey(Issuer, null=True, blank=True, on_delete=models.PROTECT)
    fingerprint = models.CharField(max_length=100, db_index=True)
    is_deleted = models.BooleanField(default=False)
    consents = JSONField(default=list)
    hash = models.CharField(null=True, blank=True, max_length=255, db_index=True)
    formatted_images = JSONField(default=dict, blank=True)
    pll_links = JSONField(default=list)
    agent_data = JSONField(default=dict, null=True, blank=True)

    all_objects = models.Manager()
    objects = PaymentCardAccountManager()

    def __str__(self):
        return '{} - {}'.format(
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


class ProviderStatusMapping(models.Model):
    provider = models.ForeignKey('payment_card.PaymentCard', on_delete=models.CASCADE)
    provider_status_code = models.CharField(max_length=24)
    bink_status_code = models.IntegerField(choices=PaymentCardAccount.STATUSES)


class AuthTransaction(models.Model):
    payment_card_account = models.ForeignKey('PaymentCardAccount', on_delete=models.SET_NULL, null=True)
    time = models.DateTimeField()
    amount = models.IntegerField()
    mid = models.CharField(max_length=100)
    third_party_id = models.CharField(max_length=100)
    auth_code = models.CharField(max_length=100, blank=True, default='')
    currency_code = models.CharField(max_length=3, default='GBP')

    def __str__(self):
        return 'Auth transaction of {}{}'.format(self.currency_code, self.amount / 100)


class PaymentStatus(IntEnum):
    PURCHASE_PENDING = 0  # Starting payment process but no purchase request has yet been made to Spreedly
    PURCHASE_FAILED = 1  # Purchase request to Spreedly has failed
    AUTHORISED = 2  # Purchase request to Spreedly was successful but Join is not complete
    SUCCESSFUL = 3  # Purchase request to Spreedly was successful and Join is completed with active card
    VOID_REQUIRED = 4  # Purchase request requires Voiding when Join fails
    VOID_SUCCESSFUL = 5  # Successfully Voided a purchase


def _generate_tx_ref() -> str:
    prefix = 'BNK-'
    identifier = uuid.uuid4()

    return '{}{}'.format(prefix, identifier)


class PaymentAudit(models.Model):
    user_id = models.CharField(max_length=255)
    scheme_account = models.ForeignKey(SchemeAccount, null=True, on_delete=models.SET_NULL)
    payment_card_hash = models.CharField(max_length=255)
    payment_card_id = models.IntegerField(null=True, blank=True)
    transaction_ref = models.CharField(max_length=255, default=_generate_tx_ref)
    transaction_token = models.CharField(max_length=255, blank=True, default='')
    status = models.IntegerField(
        choices=[(status.value, status.name) for status in PaymentStatus],
        default=PaymentStatus.PURCHASE_PENDING
    )
    void_attempts = models.IntegerField(default=0)
    created_on = models.DateTimeField(auto_now_add=True)
    modified_on = models.DateTimeField(auto_now=True)

    def __str__(self):
        return 'PaymentAudit id: {} - User id: {} - SchemeAccount id: {}'.format(
            self.id, self.user_id, self.scheme_account_id
        )
