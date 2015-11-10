from django.test import SimpleTestCase
from unittest.mock import Mock
from scheme.account_status_summary import convert_to_dictionary
from rest_framework.utils.serializer_helpers import ReturnDict


class TestStatusSummary(SimpleTestCase):

    def test_convert_to_dictionary(self):
        # Mocking
        cursor = Mock()
        test_dict = convert_to_dictionary(cursor)
        self.assertEqual(type(test_dict), ReturnDict)
