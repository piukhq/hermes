from django.utils.text import slugify
import factory
from factory.fuzzy import FuzzyAttribute
from scheme import models
from faker import Factory
from user.tests.factories import UserFactory

fake = Factory.create()


class CategoryFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.Category

    name = fake.safe_color_name()


class SchemeFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.Scheme

    name = fake.company()
    slug = FuzzyAttribute(fake.slug)
    url = fake.url()
    company = fake.company()
    company_url = fake.url()
    forgotten_password_url = fake.url()
    tier = 1
    is_barcode = True
    barcode_type = 1
    scan_message = fake.sentence()
    point_conversion_rate = 1
    category = factory.SubFactory(CategoryFactory)


class SchemeAccountFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.SchemeAccount

    user = factory.SubFactory(UserFactory)
    scheme = factory.SubFactory(SchemeFactory)
    status = 0


class SchemeCredentialQuestionFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.SchemeCredentialQuestion

    scheme = factory.SubFactory(SchemeFactory)
    type = 'username'
    label = 'Please enter your username.'


class SchemeCredentialAnswerFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.SchemeAccountCredentialAnswer

    scheme_account = factory.SubFactory(SchemeAccountFactory)
    type = 'username'
    answer = fake.first_name()
