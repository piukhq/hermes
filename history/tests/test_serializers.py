from django.test import TestCase

from history.serializers import (
    _get_serializer,
    get_historical_serializer,
    get_body_serializer,
    PaymentCardAccountSerializer,
    SchemeAccountSerializer,
    HistoricalPaymentCardAccountSerializer,
    HistoricalPaymentCardAccountEntrySerializer,
    HistoricalSchemeAccountSerializer,
    HistoricalSchemeAccountEntrySerializer
)
from payment_card.models import PaymentCardAccount


class TestSerializer(TestCase):

    def test_get_serializer(self):
        payment_card_account = 'PaymentCardAccount'
        result = _get_serializer(payment_card_account)

        self.assertEqual(result, PaymentCardAccount)

    def test_get_historical_serializer(self):
        names = ['PaymentCardAccount', 'PaymentCardAccountEntry', 'SchemeAccount', 'SchemeAccountEntry']
        expected_result = [
            HistoricalPaymentCardAccountSerializer,
            HistoricalPaymentCardAccountEntrySerializer,
            HistoricalSchemeAccountSerializer,
            HistoricalSchemeAccountEntrySerializer
        ]

        for count, name in enumerate(names):
            result = get_historical_serializer(name)

            self.assertEqual(result, expected_result[count])

    def test_get_body_serializer(self):
        names = ['PaymentCardAccount', 'SchemeAccount']
        expected_result = [PaymentCardAccountSerializer, SchemeAccountSerializer]

        for count, name in enumerate(names):
            result = get_body_serializer(name)

            self.assertEqual(result, expected_result[count])
