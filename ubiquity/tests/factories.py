import factory

from payment_card.tests.factories import PaymentCardAccountFactory
from scheme.tests.factories import SchemeAccountFactory
from ubiquity.models import PaymentCardSchemeEntry


class PaymentCardSchemeEntryFactory(factory.DjangoModelFactory):
    class Meta:
        model = PaymentCardSchemeEntry

    payment_card_account = factory.SubFactory(PaymentCardAccountFactory)
    scheme_account = factory.SubFactory(SchemeAccountFactory)
