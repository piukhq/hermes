import base64
import os
import random
import uuid
from string import ascii_letters, digits

import arrow
import jwt
from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.fields import CharField
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import ugettext_lazy as _
from hashids import Hashids

from scheme.models import Scheme
from user.managers import CustomUserManager
from user.validators import validate_boolean, validate_number

hash_ids = Hashids(alphabet='abcdefghijklmnopqrstuvwxyz1234567890', min_length=4, salt=settings.HASH_ID_SALT)

BINK_APP_ID = 'MKd3FfDGBi1CIUQwtahmPap64lneCa2R6GvVWKg6dNg4w9Jnpd'


def valid_promo_code(promo_code):
    valid = False

    if valid_marketing_code(promo_code):
        return True

    pk = hash_ids.decode(promo_code)
    if pk and CustomUser.objects.filter(id=pk[0], is_active=True).exists():
        valid = True
    return valid


def valid_marketing_code(marketing_code):
    valid = False
    try:
        mc = MarketingCode.objects.get(code=marketing_code)
        now = arrow.utcnow().datetime
        if mc.date_from <= now < mc.date_to:
            valid = True
    except MarketingCode.DoesNotExist:
        # not found
        valid = False
    return valid


class ModifyingFieldDescriptor(object):
    """ Modifies a field when set using the field's (overriden) .to_python() method. """

    def __init__(self, field):
        self.field = field

    def __get__(self, instance, owner=None):
        if instance is None:
            raise AttributeError('Can only be accessed via an instance.')
        return instance.__dict__[self.field.name]

    def __set__(self, instance, value):
        instance.__dict__[self.field.name] = self.field.to_python(value)


class LowerCaseCharField(CharField):
    def to_python(self, value):
        value = super(LowerCaseCharField, self).to_python(value)
        if isinstance(value, str):
            return value.lower()
        return value

    def contribute_to_class(self, cls, name):
        super(LowerCaseCharField, self).contribute_to_class(cls, name)
        setattr(cls, self.name, ModifyingFieldDescriptor(self))


class MarketingCode(models.Model):
    code = LowerCaseCharField(max_length=100, null=True, blank=True)
    date_from = models.DateTimeField()
    date_to = models.DateTimeField()
    description = models.CharField(max_length=300, null=True, blank=True)
    partner = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return "{0} code for partner {1}".format(self.code, self.partner)


class Organisation(models.Model):
    """A partner organisation wishing to access the Bink API.
    """
    name = models.CharField(max_length=100, unique=True)
    terms_and_conditions = models.TextField(blank=True)

    def __str__(self):
        return self.name


def _get_random_string(length=50, chars=(ascii_letters + digits)):
    rand = random.SystemRandom()
    return ''.join(rand.choice(chars) for x in range(length))


class ClientApplication(models.Model):
    """A registered API app consumer. Randomly generated client_id and secret fields.
    """
    client_id = models.CharField(max_length=128, primary_key=True, default=_get_random_string, db_index=True)
    secret = models.CharField(max_length=128, unique=False, default=_get_random_string, db_index=True)
    organisation = models.ForeignKey(Organisation, on_delete=models.PROTECT)
    name = models.CharField(max_length=100, unique=True)
    bink_app = None

    def __str__(self):
        return '{} by {}'.format(self.name, self.organisation.name)

    @classmethod
    def get_bink_app(cls):
        if not cls.bink_app:
            cls.bink_app = cls.objects.get(client_id=BINK_APP_ID)
        return cls.bink_app


class ClientApplicationBundle(models.Model):
    """Links a ClientApplication to one or more native app 'bundles'.
    """
    client = models.ForeignKey(ClientApplication, on_delete=models.PROTECT)
    bundle_id = models.CharField(max_length=200)
    issuer = models.ManyToManyField('payment_card.Issuer', blank=True)
    scheme = models.ManyToManyField('scheme.Scheme', blank=True, through='scheme.SchemeBundleAssociation',
                                    related_name='related_bundle')

    class Meta:
        unique_together = ('client', 'bundle_id',)

    @classmethod
    def get_bink_bundles(cls):
        return cls.objects.filter(client_id=BINK_APP_ID)

    @staticmethod
    def is_authenticated():
        return True

    def __str__(self):
        return '{} ({})'.format(self.bundle_id, self.client)


class ClientApplicationKit(models.Model):
    """Link a ClientApplication to known SDK kit names for usage tracking.
    """
    client = models.ForeignKey(ClientApplication, on_delete=models.PROTECT)
    kit_name = models.CharField(max_length=50)
    is_valid = models.BooleanField(default=True)

    def __str__(self):
        return 'ClientApplication: {} - kit: {}'.format(self.client, self.kit_name)


class CustomUser(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(verbose_name='email address', max_length=255, null=True, blank=True)
    client = models.ForeignKey('user.ClientApplication', default=BINK_APP_ID, on_delete=models.PROTECT, db_index=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    uid = models.CharField(max_length=50, unique=True, default=uuid.uuid4, db_index=True)
    date_joined = models.DateTimeField(_('date joined'), auto_now_add=True)
    facebook = models.CharField(max_length=120, blank=True, null=True)
    twitter = models.CharField(max_length=120, blank=True, null=True)
    reset_token = models.CharField(max_length=255, null=True, blank=True)
    marketing_code = models.ForeignKey(MarketingCode, blank=True, null=True)
    salt = models.CharField(max_length=8)
    external_id = models.CharField(max_length=255, db_index=True, default='', blank=True)

    USERNAME_FIELD = 'uid'

    REQUIRED_FIELDS = ['email']
    objects = CustomUserManager()

    class Meta:
        db_table = 'user'

    def get_full_name(self):
        return self.email

    def get_short_name(self):
        return self.email

    @property
    def referral_code(self):
        return hash_ids.encode(self.id)

    def get_expiry_date(self):
        return arrow.utcnow().replace(hours=+3)

    def generate_reset_token(self):
        expiry_date = self.get_expiry_date()
        payload = {
            'email': self.email,
            'expiry_date': expiry_date.timestamp
        }
        reset_token = jwt.encode(payload, self.client.secret)
        self.reset_token = reset_token
        self.save()
        return reset_token

    def generate_salt(self):
        self.salt = base64.b64encode(os.urandom(16))[:8].decode('utf-8')

    def create_referral(self, referral_code):
        if Referral.objects.filter(recipient=self).exists():
            return

        decoded = hash_ids.decode(referral_code)

        if decoded:
            referrer_id = decoded[0]
            Referral.objects.create(referrer_id=referrer_id, recipient_id=self.id)

    def apply_marketing(self, marketing_code):
        if self.marketing_code:
            return
        try:
            mc = MarketingCode.objects.get(code=marketing_code)
            if valid_marketing_code(mc.code):
                self.marketing_code = mc
                self.save()
            else:
                return False
        except MarketingCode.DoesNotExist:
            return False
        return True

    def apply_promo_code(self, promo_code):
        # if it's a marketing code then treat it as such, else do the promo/referral thing...
        if not self.apply_marketing(promo_code.lower()):
            self.create_referral(promo_code)

    def __unicode__(self):
        return self.email or str(self.uid)

    def __str__(self):
        return 'id: {} - {}'.format(self.id, self.email) or str(self.uid)

    # Maybe required?
    def get_group_permissions(self, obj=None):
        return set()

    def get_all_permissions(self, obj=None):
        return set()

    def has_perm(self, perm, obj=None):
        return True

    def has_perms(self, perm_list, obj=None):
        return True

    def has_module_perms(self, app_label):
        return True

    def create_token(self, bundle_id=''):
        payload = {
            'bundle_id': bundle_id,
            'sub': self.id,
            'iat': arrow.utcnow().datetime,
        }
        token = jwt.encode(payload, self.client.secret + self.salt)
        return token.decode('unicode_escape')

    # Admin required fields
    # @property
    # def is_superuser(self):
    #     return self.is_superuser


NOTIFICATIONS_SETTING = (
    (0, False),
    (1, True),
)

GENDERS = (
    ('female', 'Female'),
    ('male', 'Male'),
    ('other', 'Other'),
)


class UserDetail(models.Model):
    user = models.OneToOneField(CustomUser, related_name='profile')
    first_name = models.CharField(max_length=255, null=True, blank=True)
    last_name = models.CharField(max_length=255, null=True, blank=True)
    gender = models.CharField(max_length=6, null=True, blank=True, choices=GENDERS)
    date_of_birth = models.DateField(null=True, blank=True)
    phone = models.CharField(max_length=100, null=True, blank=True)
    address_line_1 = models.CharField(max_length=255, null=True, blank=True)
    address_line_2 = models.CharField(max_length=255, null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    region = models.CharField(max_length=100, null=True, blank=True)
    postcode = models.CharField(max_length=20, null=True, blank=True)
    # TODO: Country should not be a varchar
    country = models.CharField(max_length=100, null=True, blank=True)
    notifications = models.IntegerField(null=True, blank=True, choices=NOTIFICATIONS_SETTING)
    pass_code = models.CharField(max_length=20, null=True, blank=True)
    currency = models.CharField(max_length=3, default='GBP', null=True, blank=True)

    def __str__(self):
        return str(self.user_id)

    def set_field(self, field, value):
        if hasattr(self, field):
            return setattr(self, field, value)

        field_mapping = {
            'address_line_1': ['address_1'],
            'address_line_2': ['address_2'],
            'city': ['town_city']
        }
        for user_field in field_mapping.keys():
            if field in field_mapping[user_field]:
                return setattr(self, user_field, value)
        else:
            raise AttributeError('cant set {} field in user profile'.format(field))


class Referral(models.Model):
    referrer = models.ForeignKey(CustomUser, related_name='referrer')
    recipient = models.OneToOneField(CustomUser, related_name='recipient')
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return "{0} referred {1}".format(self.referrer, self.recipient)


@receiver(post_save, sender=CustomUser)
def create_user_detail(sender, instance, created, **kwargs):
    if created:
        UserDetail.objects.create(user=instance)


def valid_reset_code(reset_token):
    try:
        user = CustomUser.objects.get(reset_token=reset_token)
    except CustomUser.DoesNotExist:
        return False
    except CustomUser.MultipleObjectsReturned:
        return False

    token_payload = jwt.decode(reset_token, user.client.secret)
    expiry_date = arrow.get(token_payload['expiry_date'])
    return expiry_date > arrow.utcnow()


class Setting(models.Model):
    NUMBER = 0
    STRING = 1
    BOOLEAN = 2

    VALUE_TYPES = (
        (NUMBER, 'number'),
        (STRING, 'string'),
        (BOOLEAN, 'boolean'),
    )

    GENERAL = 0
    MARKETING = 1
    SCHEME = 2

    CATEGORIES = (
        (GENERAL, 'General'),
        (MARKETING, 'Marketing'),
        (SCHEME, 'Loyalty Scheme'),
    )

    slug = models.SlugField(unique=True)
    value_type = models.IntegerField(choices=VALUE_TYPES)
    default_value = models.CharField(max_length=255)
    scheme = models.ForeignKey(Scheme, null=True, blank=True)
    label = models.CharField(max_length=255, null=True, blank=True)
    category = models.IntegerField(choices=CATEGORIES, null=True, blank=True)

    @property
    def value_type_name(self):
        return dict(self.VALUE_TYPES).get(self.value_type)

    @property
    def category_name(self):
        return dict(self.CATEGORIES).get(self.category)

    def __str__(self):
        return '({}) {}: {}'.format(self.value_type_name, self.slug, self.default_value)

    def clean(self):
        validate_setting_value(self.default_value, self)


setting_value_type_validators = {
    Setting.BOOLEAN: validate_boolean,
    Setting.NUMBER: validate_number,
}


class UserSetting(models.Model):
    created_on = models.DateTimeField(auto_now_add=True)
    modified_on = models.DateTimeField(auto_now=True)
    user = models.ForeignKey(CustomUser, related_name='user')
    setting = models.ForeignKey(Setting, related_name='setting')
    value = models.CharField(max_length=255)

    def __str__(self):
        return '{} - {}: {}'.format(self.user.email, self.setting.slug, self.value)

    def clean(self):
        validate_setting_value(self.value, self.setting)

    def to_boolean(self):
        try:
            return bool(int(self.value))
        except ValueError:
            return None


def validate_setting_value(value, setting):
    # not all value_types have a corresponding validator.
    if setting.value_type in setting_value_type_validators:
        validate = setting_value_type_validators[setting.value_type]
        if not validate(value):
            raise ValidationError(_("'%(value)s' is not a valid value for type %(value_type)s."),
                                  code='invalid_value',
                                  params={
                                      'value': value,
                                      'value_type': setting.value_type_name,
                                  })
