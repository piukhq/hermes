import base64
import os

from factory.fuzzy import FuzzyAttribute
from django.utils import timezone
from faker import Factory
import factory

from user import models

fake = Factory.create()
# Change seed value if we start getting duplicate data
fake.seed(12345)


class UserFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.CustomUser

    email = FuzzyAttribute(fake.email)
    password = factory.PostGenerationMethodCall('set_password', 'defaultpassword')
    is_active = True
    is_staff = False
    salt = base64.b64encode(os.urandom(16))[:8].decode('utf-8')


class UserProfileFactory(factory.Factory):
    class Meta:
        model = models.UserDetail

    user = factory.SubFactory(UserFactory)
    first_name = fake.first_name()
    last_name = fake.last_name()
    date_of_birth = fake.date()
    phone = fake.phone_number()
    address_line_1 = fake.street_address()
    address_line_2 = fake.city()
    city = fake.city()
    region = fake.state()
    postcode = fake.postcode()
    country = 'United Kingdom'
    notifications = '0'
    pass_code = '1234'
    currency = 'GBP'
    gender = 'male'


class SettingFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.Setting
        django_get_or_create = ('slug',)

    slug = FuzzyAttribute(fake.slug)
    value_type = 2
    default_value = '0'


class UserSettingFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.UserSetting

    user = factory.SubFactory(UserFactory)
    setting = factory.SubFactory(SettingFactory)
    value = fake.text(max_nb_chars=255)


class MarketingCodeFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.MarketingCode

    code = FuzzyAttribute(fake.slug)
    date_from = timezone.now()
    date_to = timezone.now() + timezone.timedelta(days=7)
    description = fake.text(max_nb_chars=300)
    partner = fake.text(max_nb_chars=100)
