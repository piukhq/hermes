from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import BaseUserManager


class CustomUserManager(BaseUserManager):
    def _create_user(self, email, raw_password, is_staff, is_superuser, **extra_fields):
        """
        Creates and saves a User with the given username, email and password.
        """
        if email:
            email = self.normalize_email(email)

        password = make_password(raw_password)
        user = self.model(
            email=email, is_staff=is_staff, is_active=True, is_superuser=is_superuser, password=password, **extra_fields
        )
        user._password = raw_password
        user.generate_salt()
        user.save(using=self._db)
        return user

    def create_user(self, email="", password=None, **extra_fields):
        return self._create_user(email, password, is_staff=False, is_superuser=False, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        return self._create_user(email, password, is_staff=True, is_superuser=True, **extra_fields)


class IgnoreDeletedUserManager(CustomUserManager):
    def get_queryset(self):
        return super(CustomUserManager, self).get_queryset().filter(is_active=True)
