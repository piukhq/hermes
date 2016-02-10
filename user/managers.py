from django.contrib.auth.models import BaseUserManager


class CustomUserManager(BaseUserManager):
    def _create_user(self, email, password,  promo_code, is_staff, is_superuser, **extra_fields):
        """
        Creates and saves a User with the given username, email and password.
        """
        if email:
            email = self.normalize_email(email)
        user = self.model(email=email, is_staff=is_staff, is_active=True, is_superuser=is_superuser, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        if promo_code:
            user.create_referral(promo_code)
        return user

    def create_user(self, email=None, password=None, promo_code=None, **extra_fields):
        return self._create_user(email, password, promo_code, is_staff=False, is_superuser=False,
                                 **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        return self._create_user(email, password, promo_code=None, is_staff=True, is_superuser=True,
                                 **extra_fields)
