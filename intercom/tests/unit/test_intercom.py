import json
import unittest

from hermes import settings
from intercom.intercom_api import post_issued_join_card_event, ISSUED_JOIN_CARD_EVENT, reset_user_custom_attributes, \
    update_user_custom_attribute, IntercomException


@unittest.mock.patch('requests.post')
class IntercomApiTest(unittest.TestCase):

    FAKE_TOKEN = 'FAKE_TOKEN_XXx'
    FAKE_USER_ID = 'xxXX-xx-xx-XXxx'

    def setUp(self):
        patcher = unittest.mock.patch('time.time', return_value='99999999')
        self.addCleanup(patcher.stop)
        self.mock_foo = patcher.start()

    def test_post_issued_card_event_successful(self, post_mock):
        post_mock.return_value = unittest.mock.Mock(status_code=202)
        company_name = 'test_company_name'
        slug = 'test-slug'
        expected_data = {
            'user_id': self.FAKE_USER_ID,
            'event_name': ISSUED_JOIN_CARD_EVENT,
            'created_at': 99999999
        }

        post_issued_join_card_event(self.FAKE_TOKEN, self.FAKE_USER_ID, company_name, slug)

        self.assertEqual(post_mock.call_count, 1)
        call_url, call_kwargs = post_mock.call_args

        self.assertIn(
            settings.INTERCOM_EVENTS_PATH,
            call_url[0],
            'Error - Post url does not contain the intercom event path'
        )
        self.assertTrue('headers', call_kwargs)
        self.assertTrue('data', call_kwargs)

        self.assertEqual(expected_data, json.loads(call_kwargs['data']))

    def test_post_issued_card_event_unsuccessful(self, post_mock):
        post_mock.return_value = unittest.mock.Mock(status_code=400, text='mock_text')
        company_name = 'test_company_name'
        slug = 'test-slug'

        with self.assertRaises(IntercomException) as context:
            post_issued_join_card_event(self.FAKE_TOKEN, self.FAKE_USER_ID, company_name, slug)
        self.assertIn('Error post_issued_join_card_event: mock_text', str(context.exception))

    def test_reset_user_custom_attributes_successful(self, post_mock):
        post_mock.return_value = unittest.mock.Mock(status_code=200)
        expected_data = {
            'user_id': self.FAKE_USER_ID,
            'custom_attributes': {
                'marketing-bink': None,
                'marketing-external': None
            }
        }

        reset_user_custom_attributes(self.FAKE_TOKEN, self.FAKE_USER_ID)

        self.assertEqual(post_mock.call_count, 1)
        call_url, call_kwargs = post_mock.call_args

        self.assertIn(
            settings.INTERCOM_USERS_PATH,
            call_url[0],
            'Error - Post url does not contain the intercom user attributes path'
        )
        self.assertTrue('headers', call_kwargs)
        self.assertTrue('data', call_kwargs)
        self.assertEqual(expected_data, json.loads(call_kwargs['data']))

    def test_reset_user_custom_attributes_unsuccessful(self, post_mock):
        post_mock.return_value = unittest.mock.Mock(status_code=400, text='mock_text')

        with self.assertRaises(IntercomException) as context:
            reset_user_custom_attributes(self.FAKE_TOKEN, self.FAKE_USER_ID)
        self.assertIn('Error reset_user_custom_attributes: mock_text', str(context.exception))

    def test_update_user_custom_attribute_successful(self, post_mock):
        post_mock.return_value = unittest.mock.Mock(status_code=200)

        attr_name = 'attr-name'
        attr_value = '1'

        expected_data = {
            'user_id': self.FAKE_USER_ID,
            'custom_attributes': {attr_name: attr_value}
        }

        update_user_custom_attribute(self.FAKE_TOKEN, self.FAKE_USER_ID, attr_name, attr_value)

        self.assertEqual(post_mock.call_count, 1)
        call_url, call_kwargs = post_mock.call_args

        self.assertIn(
            settings.INTERCOM_USERS_PATH,
            call_url[0],
            'Error - Post url does not contain the intercom user attributes path'
        )
        self.assertTrue('headers', call_kwargs)
        self.assertTrue('data', call_kwargs)

        self.assertEqual(json.loads(call_kwargs['data']), expected_data)

    def test_update_user_custom_attribute_unsuccessful(self, post_mock):
        post_mock.return_value = unittest.mock.Mock(status_code=400, text='mock_text')

        attr_name = 'attr-name'
        attr_value = '1'
        with self.assertRaises(IntercomException) as context:
            update_user_custom_attribute(self.FAKE_TOKEN, self.FAKE_USER_ID, attr_name, attr_value)

        self.assertIn('Error update_user_custom_attribute: mock_text', str(context.exception))
