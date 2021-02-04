from django.test import TestCase

from history.enums import HistoryModel
from history.serializers import (
    get_historical_serializer,
    get_body_serializer,
    HISTORICAL_SERIALIZERS,
    BODY_SERIALIZERS
)


class TestSerializer(TestCase):

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
        expected_result = BODY_SERIALIZERS.values()

        for name in names:
            result = get_body_serializer(name)
            self.assertIn(result, expected_result)
