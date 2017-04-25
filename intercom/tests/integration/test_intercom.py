import json
import unittest

from intercom.intercom_api import update_user_attributes, post_event, get_users, get_user_events, \
    update_user_custom_attribute


class IntercomApiTest(unittest.TestCase):
    USER_ID = '45851621-391c-4d0e-aced-2dab6813cb09'
    TOKEN = 'dG9rOmE4MGYzNDRjX2U5YzhfNGQ1N184MTA0X2E4YTgwNDQ2ZGY1YzoxOjA='

    def test_get_users(self):
        response = get_users(self.TOKEN)
        self.assertEqual(response.status_code, 200, response.text)

        response_obj = json.loads(response.content)
        self.assertIn('type', response_obj)
        self.assertEqual(response_obj['type'], 'user.list')

    def test_get_user_events(self):
        response = get_user_events(self.TOKEN, self.USER_ID)
        self.assertEqual(response.status_code, 200, response.text)

        response_obj = json.loads(response.content)
        self.assertIn('type', response_obj)
        self.assertEqual(response_obj['type'], 'event.list')
        self.assertIn('events', response_obj)

    def test_post_event(self):
        test_event_name = 'issued-join-card'

        # get initial event count
        response_get = get_user_events(self.TOKEN, self.USER_ID)
        response_obj = json.loads(response_get.content)
        test_events = [event for event in response_obj['events'] if event['event_name'] == test_event_name]
        initial_event_count = len(test_events)

        # post a new event
        response_post = post_event(self.TOKEN, self.USER_ID, test_event_name)
        self.assertEqual(response_post.status_code, 202, response_post.text)

        # get the new event count
        response_get = get_user_events(self.TOKEN, self.USER_ID)
        response_obj = json.loads(response_get.content)
        self.assertIn('events', response_obj)
        test_events = [event for event in response_obj['events'] if event['event_name'] == test_event_name]
        self.assertEqual(len(test_events), initial_event_count + 1)

    def test_update_custom_attribute(self):
        attr_name = 'marketing_bink'
        attr_value = False

        response = update_user_custom_attribute(self.TOKEN, self.USER_ID, attr_name, attr_value)
        self.assertEqual(response.status_code, 200, response.text)

        response_obj = json.loads(response.content)
        self.assertIn('custom_attributes', response_obj)
        self.assertIs(response_obj['custom_attributes'][attr_name], False)

    def test_update_user_marketing_bink(self):
        attr = {
            'custom_attributes': {
                'marketing bink': True,
                'marketing external': True
            }
        }
        response = update_user_attributes(self.TOKEN, self.USER_ID, attr)
        self.assertEqual(response.status_code, 200, response.text)

        response_obj = json.loads(response.content)
        self.assertIn('custom_attributes', response_obj)
        self.assertIs(response_obj['custom_attributes']['marketing bink'], True)
        self.assertIs(response_obj['custom_attributes']['marketing external'], True)
