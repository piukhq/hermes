from datetime import datetime
import uuid
import factory

from factory.fuzzy import FuzzyAttribute
from faker import Factory
from django.utils import timezone

from user.tests.factories import UserFactory
from payment_card import models

fake = Factory.create()


class IssuerFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.Issuer


class PaymentCardFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.PaymentCard
        django_get_or_create = ('slug',)

    name = fake.word()
    slug = FuzzyAttribute(fake.slug)
    url = fake.url()
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
    fingerprint = FuzzyAttribute(uuid.uuid4)


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
    end_date = timezone.make_aware(datetime(2200, 1, 1))


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
    reward_tier = ""

    order = 0

    payment_card = factory.SubFactory(PaymentCardFactory)

    start_date = timezone.now()
    end_date = timezone.make_aware(datetime(2200, 1, 1))

    status = models.PaymentCardAccountImage.PUBLISHED
