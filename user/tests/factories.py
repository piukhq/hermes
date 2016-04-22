import factory
from factory.fuzzy import FuzzyAttribute
from user import models
from faker import Factory


fake = Factory.create()


class UserFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.CustomUser

    email = FuzzyAttribute(fake.email)
    password = factory.PostGenerationMethodCall('set_password', 'defaultpassword')
    is_active = True
    is_staff = False


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

    slug = FuzzyAttribute(fake.slug)
    value_type = 2
    default_value = False


class UserSettingFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.UserSetting

    user = factory.SubFactory(UserFactory)
    setting = factory.SubFactory(SettingFactory)
    value = fake.text(max_nb_chars=255)
