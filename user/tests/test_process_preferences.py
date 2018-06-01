from django.test import TestCase
from user.views import process_preferences
from user.models import Setting
from scheme.tests.factories import SchemeCredentialQuestionFactory
from scheme.tests.factories import SchemeImageFactory
from scheme.tests.factories import SchemeFactory
from scheme.tests.factories import SettingsFactory
from scheme.credentials import EMAIL, BARCODE, CARD_NUMBER
from scheme.models import SchemeCredentialQuestion
from user.tests.factories import UserFactory
from user.models import UserSetting
from faker import Factory
import random

fake = Factory.create()

class SimulatedRequest:
    def __init__(self, user,  values):
        self.other = {}
        self.user = user
        self.data = {"preferences": values, "other_info": "data"}


def create_scheme():
    scheme = SchemeFactory()
    SchemeImageFactory(scheme=scheme)
    SchemeCredentialQuestionFactory.create(
        scheme=scheme,
        type=fake.email,
        options=SchemeCredentialQuestion.LINK)
    SchemeCredentialQuestionFactory.create(
        scheme=scheme,
        type=CARD_NUMBER,
        options=SchemeCredentialQuestion.JOIN,
        manual_question=True)
    SchemeCredentialQuestionFactory(scheme=scheme, type=BARCODE, manual_question=True)
    return scheme


class TestProcessPreferences(TestCase):

    def test_preferences_are_set(self):
        scheme = create_scheme()
        test_default_string = fake.text(max_nb_chars=255)
        test_default_number = random.randint(0,10000)
        test_actual_string = fake.text(max_nb_chars=255)
        test_actual_number = random.randint(0,10000)
        user = UserFactory()
        setting1 = SettingsFactory.create(
            scheme=scheme, journey=Setting.LINK_JOIN, slug="pref1", order=1, value_type=Setting.STRING,
            default_value=test_default_string
        )
        setting2 = SettingsFactory.create(
            scheme=scheme, journey=Setting.LINK_JOIN, slug="pref2", order=2, value_type=Setting.NUMBER,
            default_value=test_default_number
        )
        mock_request = SimulatedRequest(user, {"pref1": test_actual_string, "pref2": test_actual_number})
        result = process_preferences(mock_request)
        self.assertNotIn('preferences', mock_request.data, "Preferences not removed from request")
        self.assertEqual(result, [], "Setting preferences found unexpected errors bad slugs?")
        set_values = UserSetting.objects.filter(user=user).values()
        self.assertEqual(len(set_values), 2, "Too many preferences settings were found")
        for set_value in set_values:
            if set_value['setting_id'] == setting1.id:
                self.assertEqual(set_value['value'], test_actual_string)
            elif set_value['setting_id'] == setting2.id:
                self.assertEqual(int(set_value['value']), test_actual_number)
            else:
                self.assertTrue(False, "Unknown preference found")

    def test_for_unknown_preferences_slugs(self):
        scheme = create_scheme()
        test_default_string = fake.text(max_nb_chars=255)
        test_default_number = random.randint(0, 10000)
        test_actual_string = fake.text(max_nb_chars=255)
        test_actual_number = random.randint(0, 10000)
        user = UserFactory()
        SettingsFactory.create(
            scheme=scheme, journey=Setting.LINK_JOIN, slug="pref1", order=1, value_type=Setting.STRING,
            default_value=test_default_string
        )
        SettingsFactory.create(
            scheme=scheme, journey=Setting.LINK_JOIN, slug="pref2", order=2, value_type=Setting.NUMBER,
            default_value=test_default_number
        )
        mock_request = SimulatedRequest(user, {"bad_pref": test_actual_string, "pref2": test_actual_number})
        result = process_preferences(mock_request)
        self.assertNotIn('preferences', mock_request.data, "Preferences not removed from request")
        self.assertEqual(result, ['bad_pref'], "Setting preferences found unexpected errors bad slugs?")
        set_values = UserSetting.objects.filter(user=user).values()
        self.assertEqual(len(set_values), 0, "Everything should have been rejected")

