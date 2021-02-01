from django.test import TestCase

from history.enums import HistoryModel
from history.serializers import (
    _get_serializer,
    get_historical_serializer,
    get_body_serializer,
    PaymentCardAccountSerializer,
    SchemeAccountSerializer,
    HISTORICAL_SERIALIZERS
)
from payment_card.models import PaymentCardAccount


class TestSerializer(TestCase):

    def test_get_serializer(self):
        payment_card_account = 'PaymentCardAccount'
        result = _get_serializer(payment_card_account)

        self.assertEqual(result, PaymentCardAccount)

    def test_get_historical_serializer(self):
        names = [
            history_model.model_name
            for history_model in HistoryModel
        ]

        expected_result = [
            HISTORICAL_SERIALIZERS[history_model.historic_serializer_name]
            for history_model in HistoryModel
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
