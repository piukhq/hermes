from django.test import SimpleTestCase
from scheme.account_status_summary import scheme_account_status_data
from unittest.mock import patch
from scheme.tests.fixtures import summary_scheme_data


@patch('scheme.account_status_summary.status_summary_from_db')
class TestStatusSummary(SimpleTestCase):

    def test_convert_to_dictionary(self, mock_status_summary_from_db):
        mock_status_summary_from_db.return_value = summary_scheme_data
        test_dict = scheme_account_status_data()
        self.assertTrue(isinstance(test_dict, list))
        self.assertTrue(isinstance(test_dict[0], dict))
        self.assertTrue(isinstance(test_dict[0]['statuses'], list))
        self.assertTrue(len(test_dict[0]['statuses']) > 0)
        self.assertTrue(isinstance(test_dict[0]['scheme_id'], int))


