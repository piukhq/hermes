import factory
from faker import Factory
from payment_card import models
from user.tests.factories import UserFactory

fake = Factory.create()


class IssuerFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.Issuer


class PaymentCardFactory(factory.DjangoModelFactory):
    class Meta:
        model = models.PaymentCard

    name = fake.word()
    slug = fake.slug()
    url = fake.url()
    image = fake.image_url()
    scan_message = fake.bs()
    input_label = fake.bs()
    system = models.PaymentCard.MATERCARD
    type = models.PaymentCard.MATERCARD


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
