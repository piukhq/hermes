import uuid
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from user.managers import CustomUserManager
from django.utils.translation import ugettext_lazy as _
from django.utils import timezone


class CustomUser(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(verbose_name='email address', max_length=255, unique=True, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    uid = models.CharField(max_length=50, unique=True, default=uuid.uuid4)
    date_joined = models.DateTimeField(_('date joined'), default=timezone.now)
    facebook = models.CharField(max_length=120, blank=True, null=True)
    twitter = models.CharField(max_length=120, blank=True, null=True)

    USERNAME_FIELD = 'uid'

    objects = CustomUserManager()

    class Meta:
        db_table = 'user'

    def get_full_name(self):
        return self.uid

    def get_short_name(self):
        return self.uid

    def __unicode__(self):
        return self.email or str(self.uid)

    def __str__(self):
        return str(self.uid)

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

    # # Admin required fields
    # @property
    # def is_superuser(self):
    #     return self.is_superuser

NOTIFICATIONS_SETTING = (
    (0, False),
    (1, True),
)


class UserDetail(models.Model):
    user = models.OneToOneField(CustomUser, related_name='profile')
    first_name = models.CharField(max_length=255, null=True, blank=True)
    last_name = models.CharField(max_length=255, null=True, blank=True)
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
    # avatar

    def __str__(self):
        return str(self.user_id)


@receiver(post_save, sender=CustomUser)
def create_user_detail(sender, instance, created, **kwargs):
    if created:
        UserDetail.objects.create(user=instance)
