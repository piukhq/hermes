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
    barcode_type = 1
    scan_message = fake.sentence()
    point_conversion_rate = 1
    input_label = fake.word()
    category = factory.SubFactory(CategoryFactory)


class SchemeAccountFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.SchemeAccount

    user = factory.SubFactory(UserFactory)
    scheme = factory.SubFactory(SchemeFactory)
    username = fake.user_name()
    card_number = fake.credit_card_number()
    membership_number = fake.pyint()
    password = fake.password()
    status = 0


class SchemeAccountSecurityQuestionFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.SchemeAccountSecurityQuestion

    scheme_account = factory.SubFactory(SchemeAccountFactory)
    question = fake.sentence()
    answer = fake.password()
