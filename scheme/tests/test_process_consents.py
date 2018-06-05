from django.test import TestCase
from scheme.views import process_consents
from scheme.models import Consent
from scheme.tests.factories import SchemeCredentialQuestionFactory
from scheme.tests.factories import SchemeImageFactory
from scheme.tests.factories import SchemeFactory
from scheme.tests.factories import ConsentFactory
from scheme.credentials import BARCODE, CARD_NUMBER
from scheme.models import SchemeCredentialQuestion
from user.tests.factories import UserFactory
from scheme.models import UserConsent
from faker import Factory
import random

fake = Factory.create()


class SimulatedRequest:
    def __init__(self, user,  values):
        self.other = {}
        self.user = user
        self.data = {"consents": values, "other_info": "data"}


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


class TestProcessConsents(TestCase):

    def test_consents_are_set(self):
        scheme = create_scheme()
        test_default_string = fake.text(max_nb_chars=255)

        user = UserFactory()
        consent1 = ConsentFactory.create(
            scheme=scheme, journey=Consent.LINK, slug="pref1", order=1,
            text=test_default_string
        )
        consent2 = ConsentFactory.create(
            scheme=scheme, journey=Consent.JOIN, slug="pref2", order=2,
        )
        mock_request = SimulatedRequest(user, {"pref1": '0', "pref2": '1'})
        result = process_consents(mock_request)
        self.assertNotIn('consents', mock_request.data, "Consents not removed from request")
        self.assertEqual(result, [], "Consents were found ie unexpected errors bad slugs?")
        set_values = UserConsent.objects.filter(user=user).values()
        self.assertEqual(len(set_values), 2, "Did not find expected number of consents in UserConsent table")
        for set_value in set_values:
            if set_value['consent_id'] == consent1.id:
                self.assertEqual(set_value['value'], '0')
            elif set_value['consent_id'] == consent2.id:
                self.assertEqual(set_value['value'], '1')
            else:
                self.assertTrue(False, "Unknown preference found")

    def test_for_unknown_preferences_slugs(self):
        scheme = create_scheme()
        test_actual_string = fake.text(max_nb_chars=255)
        test_actual_number = random.randint(0, 10000)
        user = UserFactory()
        ConsentFactory.create(
            scheme=scheme, journey=Consent.LINK, slug="pref1", order=1,
        )
        ConsentFactory.create(
            scheme=scheme, journey=Consent.JOIN, slug="pref2", order=2,
        )
        mock_request = SimulatedRequest(user, {"bad_pref": test_actual_string, "pref2": test_actual_number})
        result = process_consents(mock_request)
        self.assertNotIn('consents', mock_request.data, "Consents not removed from request")
        self.assertEqual(result, ['bad_pref'], "Unexpected Consent found: bad slug?")
        set_values = UserConsent.objects.filter(user=user).values()
        self.assertEqual(len(set_values), 0, "Everything should have been rejected")
