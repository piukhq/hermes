import factory
from factory.fuzzy import FuzzyAttribute
from faker import Factory
from payment_card import models
from user.tests.factories import UserFactory
from django.utils import timezone

fake = Factory.create()


class IssuerFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.Issuer


class PaymentCardFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.PaymentCard

    name = fake.word()
    slug = FuzzyAttribute(fake.slug)
    url = fake.url()
    image = fake.image_url()
    scan_message = fake.bs()
    input_label = fake.bs()
    system = models.PaymentCard.MASTERCARD
    type = models.PaymentCard.MASTERCARD


class PaymentCardAccountFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.PaymentCardAccount

    user = factory.SubFactory(UserFactory)
    payment_card = factory.SubFactory(PaymentCardFactory)
    name_on_card = fake.name()
    start_month = fake.month()
    start_year = fake.month()
    expiry_month = fake.month()
    expiry_year = fake.month()
    pan_start = 111111
    pan_end = 2222
    order = 0
    issuer = factory.SubFactory(IssuerFactory)
    fingerprint = FuzzyAttribute(fake.uuid4)


class PaymentCardImageFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.PaymentCardImage

    payment_card = factory.SubFactory(PaymentCardFactory)
    image_type_code = 1
    size_code = fake.word()
    image = fake.url()
    strap_line = fake.sentence(nb_words=3)
    description = fake.sentence(nb_words=3)
    url = fake.url()
    call_to_action = fake.sentence(nb_words=3)
    order = 0
    status = 1
    start_date = timezone.now()
    end_date = "2200-1-1"


class PaymentCardAccountImageFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.PaymentCardAccountImage

    image_type_code = 1
    size_code = fake.word()
    image = fake.url()
    strap_line = fake.sentence(nb_words=3)
    description = fake.sentence(nb_words=3)
    url = fake.url()
    call_to_action = fake.sentence(nb_words=3)
    order = 0


class PaymentCardAccountImageCriteriaFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.PaymentCardAccountImageCriteria

    payment_card = factory.SubFactory(PaymentCardFactory)
    description = fake.sentence(nb_words=3)
    start_date = timezone.now()
    end_date = "2200-1-1"
