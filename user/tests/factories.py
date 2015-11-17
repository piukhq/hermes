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
