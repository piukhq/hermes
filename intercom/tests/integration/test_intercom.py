import json
import unittest

from intercom.intercom_api import reset_user_setting, post_issued_join_card_event, \
    update_user_custom_attribute, ISSUED_JOIN_CARD_EVENT, get_user_events


@unittest.skip("Test to be used just to develop.")
class IntercomApiTest(unittest.TestCase):
    USER_ID = '45851621-391c-4d0e-aced-2dab6813cb09'
    TOKEN = 'dG9rOmE4MGYzNDRjX2U5YzhfNGQ1N184MTA0X2E4YTgwNDQ2ZGY1YzoxOjA='

    def test_post_issued_join_card_event(self):
        # get initial event count
        response_get = get_user_events(self.TOKEN, self.USER_ID)
        response_obj = json.loads(response_get.content)
        test_events = [event for event in response_obj['events'] if event['event_name'] == ISSUED_JOIN_CARD_EVENT]
        initial_event_count = len(test_events)

        # post a new event
        company_name = 'test_company_name'
        slug = 'test-slug'
        response_post = post_issued_join_card_event(self.TOKEN, self.USER_ID, company_name, slug)
        self.assertEqual(response_post.status_code, 202, response_post.text)

        # get the new event count
        response_get = get_user_events(self.TOKEN, self.USER_ID)
        response_obj = json.loads(response_get.content)
        self.assertIn('events', response_obj)
        test_events = [event for event in response_obj['events'] if event['event_name'] == ISSUED_JOIN_CARD_EVENT]
        self.assertEqual(len(test_events), initial_event_count + 1)

    def test_update_custom_attribute(self):
        attr_name = 'marketing_bink'
        attr_value = False

        response = update_user_custom_attribute(self.TOKEN, self.USER_ID, attr_name, attr_value)
        self.assertEqual(response.status_code, 200, response.text)

        response_obj = json.loads(response.content)
        self.assertIn('custom_attributes', response_obj)
        self.assertIs(response_obj['custom_attributes'][attr_name], False)

    def test_reset_custom_attributes(self):
        response = reset_user_setting(self.TOKEN, self.USER_ID)
        self.assertEqual(response.status_code, 200, response.text)

        response_obj = json.loads(response.content)
        self.assertIn('custom_attributes', response_obj)
        self.assertIs(response_obj['custom_attributes']['marketing bink'], None)
        self.assertIs(response_obj['custom_attributes']['marketing external'], None)

    def test_delete_custom_attribute(self):
        attr_name = 'marketing_bink'
        attr_value = None

        response = update_user_custom_attribute(self.TOKEN, self.USER_ID, attr_name, attr_value)
        self.assertEqual(response.status_code, 200, response.text)

        response_obj = json.loads(response.content)
        self.assertIn('custom_attributes', response_obj)
        self.assertIs(response_obj['custom_attributes'][attr_name], None)

    def test_get_user_events(self):
        response = get_user_events(self.TOKEN, self.USER_ID)
        self.assertEqual(response.status_code, 200, response.text)

        response_obj = json.loads(response.content)
        self.assertIn('type', response_obj)
        self.assertEqual(response_obj['type'], 'event.list')
        self.assertIn('events', response_obj)
