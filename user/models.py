import arrow
import jwt
import uuid
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from hashids import Hashids
from hermes import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from user.managers import CustomUserManager
from django.utils.translation import ugettext_lazy as _


hash_ids = Hashids(alphabet='abcdefghijklmnopqrstuvwxyz1234567890', min_length=4, salt=settings.HASH_ID_SALT)


def valid_promo_code(promo_code):
    pk = hash_ids.decode(promo_code)
    valid = False
    if pk and CustomUser.objects.filter(id=pk[0], is_active=True).exists():
        valid = True
    return valid


class CustomUser(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(verbose_name='email address', max_length=255, unique=True, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    uid = models.CharField(max_length=50, unique=True, default=uuid.uuid4)
    date_joined = models.DateTimeField(_('date joined'), auto_now_add=True)
    facebook = models.CharField(max_length=120, blank=True, null=True)
    twitter = models.CharField(max_length=120, blank=True, null=True)
    reset_token = models.CharField(max_length=255, null=True, blank=True)

    USERNAME_FIELD = 'uid'

    REQUIRED_FIELDS = ['email']
    objects = CustomUserManager()

    class Meta:
        db_table = 'user'

    def get_full_name(self):
        return self.uid

    def get_short_name(self):
        return self.uid

    @property
    def referral_code(self):
        return hash_ids.encode(self.id)

    def generate_reset_token(self):
        expiry_date = arrow.utcnow().replace(hours=+3)
        payload = {
            'email': self.email,
            'expiry_date': expiry_date.timestamp
        }
        reset_token = jwt.encode(payload, settings.TOKEN_SECRET)
        self.reset_token = reset_token
        self.save()
        return reset_token

    def create_referral(self, referral_code):
        referrer_id = hash_ids.decode(referral_code)[0]
        Referral.objects.create(referrer_id=referrer_id, recipient_id=self.id)

    def __unicode__(self):
        return self.email or str(self.uid)

    def __str__(self):
        return self.email or str(self.uid)

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

    def create_token(self):
        payload = {
            'sub': self.id,
            'iat': arrow.utcnow().datetime,
        }
        token = jwt.encode(payload, settings.TOKEN_SECRET)
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
        CustomUser.objects.get(reset_token=reset_token)
    except CustomUser.DoesNotExist:
        return False
    except CustomUser.MultipleObjectsReturned:
        return False

    token_payload = jwt.decode(reset_token, settings.TOKEN_SECRET)
    expiry_date = arrow.get(token_payload['expiry_date'])
    return expiry_date > arrow.utcnow()



