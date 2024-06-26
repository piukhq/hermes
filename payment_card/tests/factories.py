import uuid
from datetime import datetime

import factory
from django.utils import timezone
from factory.fuzzy import FuzzyAttribute
from faker import Factory

from payment_card import models
from payment_card.models import PaymentAudit

fake = Factory.create()
# Change seed value if we start getting duplicate data
fake.seed(12345)


class IssuerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.Issuer
        django_get_or_create = ("name",)

    name = fake.word()


class PaymentCardFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.PaymentCard
        django_get_or_create = ("slug",)

    name = fake.word()
    slug = FuzzyAttribute(fake.slug)
    url = fake.url()
    scan_message = fake.bs()
    input_label = fake.bs()
    system = models.PaymentCard.VISA
    type = models.PaymentCard.CREDIT


def gen_fingerprint() -> str:
    return str(uuid.uuid4().hex)


class PaymentCardAccountFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.PaymentCardAccount

    payment_card = factory.SubFactory(PaymentCardFactory)
    status = models.PaymentCardAccount.ACTIVE
    name_on_card = fake.name()
    start_month = fake.month()
    start_year = fake.month()
    expiry_month = fake.month()
    expiry_year = fake.month()
    currency_code = "GBP"
    pan_start = "111111"
    pan_end = "2222"
    order = 0
    issuer = factory.SubFactory(IssuerFactory)
    fingerprint = FuzzyAttribute(gen_fingerprint)
    psp_token = FuzzyAttribute(gen_fingerprint)
    token = psp_token
    issuer_name = fake.word()


class PaymentCardImageFactory(factory.django.DjangoModelFactory):
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


class PaymentCardAccountImageFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.PaymentCardAccountImage

    image_type_code = 1
    size_code = fake.word()
    image = fake.url()

    strap_line = fake.sentence(nb_words=3)
    description = fake.sentence(nb_words=3)
    url = fake.url()
    call_to_action = fake.sentence(nb_words=3)
    reward_tier = 0

    order = 0

    payment_card = factory.SubFactory(PaymentCardFactory)

    start_date = timezone.now()
    end_date = timezone.make_aware(datetime(2200, 1, 1))

    status = models.PaymentCardAccountImage.PUBLISHED


class PaymentAuditFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PaymentAudit
