from datetime import datetime

import factory

from payment_card.tests.factories import PaymentCardAccountFactory
from scheme.tests.factories import SchemeAccountFactory
from ubiquity.models import (
    PaymentCardAccountEntry,
    PaymentCardSchemeEntry,
    PllUserAssociation,
    SchemeAccountEntry,
    ServiceConsent,
    WalletPLLStatus,
)
from user.tests.factories import UserFactory


class PaymentCardAccountEntryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PaymentCardAccountEntry

    user = factory.SubFactory(UserFactory)
    payment_card_account = factory.SubFactory(PaymentCardAccountFactory)


class PaymentCardSchemeEntryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PaymentCardSchemeEntry

    payment_card_account = factory.SubFactory(PaymentCardAccountFactory)
    scheme_account = factory.SubFactory(SchemeAccountFactory)
    active_link = True


class PllUserAssociationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PllUserAssociation

    state = WalletPLLStatus.ACTIVE
    slug = ""
    pll = factory.SubFactory(PaymentCardSchemeEntryFactory)
    user = factory.SubFactory(UserFactory)


class SchemeAccountEntryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SchemeAccountEntry

    user = factory.SubFactory(UserFactory)
    scheme_account = factory.SubFactory(SchemeAccountFactory)
    auth_provided = True
    link_status = 1  # ACTIVE (default in DB is PENDING, but this makes more sense here!)


class ServiceConsentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ServiceConsent

    user = factory.SubFactory(UserFactory)
    timestamp = datetime(2019, 1, 1, 12, 00)
