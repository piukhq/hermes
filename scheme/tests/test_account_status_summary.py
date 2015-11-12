from django.test import SimpleTestCase
from scheme.account_status_summary import scheme_summary_list
from scheme.tests.fixtures import summary_scheme_data



class TestStatusSummary(SimpleTestCase):
    def test_convert_to_dictionary(self):
        test_dict = scheme_summary_list(summary_scheme_data)
        self.assertTrue(isinstance(test_dict, list))
        self.assertTrue(isinstance(test_dict[0], dict))
        self.assertTrue(isinstance(test_dict[0]['statuses'], list))
        self.assertTrue(len(test_dict[0]['statuses']) > 0)
        self.assertTrue(isinstance(test_dict[0]['scheme_id'], int))
