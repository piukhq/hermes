import factory

from payment_card.tests.factories import PaymentCardAccountFactory
from scheme.tests.factories import SchemeAccountFactory
from ubiquity.models import PaymentCardAccountEntry, PaymentCardSchemeEntry, SchemeAccountEntry
from user.tests.factories import UserFactory


class PaymentCardAccountEntryFactory(factory.DjangoModelFactory):
    class Meta:
        model = PaymentCardAccountEntry

    user = factory.SubFactory(UserFactory)
    payment_card_account = factory.SubFactory(PaymentCardAccountFactory)


class PaymentCardSchemeEntryFactory(factory.DjangoModelFactory):
    class Meta:
        model = PaymentCardSchemeEntry

    payment_card_account = factory.SubFactory(PaymentCardAccountFactory)
    scheme_account = factory.SubFactory(SchemeAccountFactory)


class SchemeAccountEntryFactory(factory.DjangoModelFactory):
    class Meta:
        model = SchemeAccountEntry

    user = factory.SubFactory(UserFactory)
    scheme_account = factory.SubFactory(SchemeAccountFactory)
