import arrow
from django.test import TestCase
from rest_framework.test import APITestCase

from ubiquity.tests.factories import SchemeAccountEntryFactory
from ubiquity.tests.property_token import GenerateJWToken
from user.models import CustomUser
from user.tests.factories import ClientApplicationBundleFactory


class TestViews(APITestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = ClientApplicationBundleFactory()
        cls.token_generator = GenerateJWToken
        super().setUpClass()

    def test_service_registration(self):
        data = {
            'client_id': self.bundle.client.client_id,
            'secret': self.bundle.client.secret,
            'bundle_id': self.bundle.bundle_id
        }
        token = self.token_generator(**data).get_token()
        auth_headers = {'HTTP_AUTHORIZATION': 'token {}'.format(token)}
        consent = {
            'latitude': 12.234,
            'longitude': 56.856,
            'timestamp': arrow.utcnow().timestamp
        }

        resp = self.client.post('/ubiquity/service', data=consent, **auth_headers)
        self.assertEqual(resp.status_code, 200)

    def test_service_registration_wrong_data(self):
        data = {
            'client_id': self.bundle.client.client_id,
            'secret': self.bundle.client.secret,
            'bundle_id': self.bundle.bundle_id,
            'email': 'wrongconsent@bink.test'
        }
        token = self.token_generator(**data).get_token()
        auth_headers = {'HTTP_AUTHORIZATION': 'token {}'.format(token)}
        consent = {
            'latitude': 12.234,
            'longitude': 56.856,
            'timestamp': 'not a timestamp'
        }

        wrong_consent_resp = self.client.post('/ubiquity/service', data=consent, **auth_headers)
        self.assertEqual(wrong_consent_resp.status_code, 400)
        self.assertIn('timestamp', wrong_consent_resp.json())

        with self.assertRaises(CustomUser.DoesNotExist):
            CustomUser.objects.get(email='{}__{}'.format(data['bundle_id'], data['email']))

    def test_service_registration_wrong_header(self):
        data = {
            'client_id': self.bundle.client.client_id,
            'secret': self.bundle.client.secret,
            'bundle_id': 'wrong bundle id'
        }
        token = self.token_generator(**data).get_token()
        auth_headers = {'HTTP_AUTHORIZATION': 'token {}'.format(token)}
        consent = {
            'latitude': 12.234,
            'longitude': 56.856,
            'timestamp': arrow.utcnow().timestamp
        }

        wrong_header_resp = self.client.post('/ubiquity/service', data=consent, **auth_headers)
        self.assertEqual(wrong_header_resp.status_code, 403)
        self.assertIn('Invalid token', wrong_header_resp.json()['detail'])


class TestBalance(TestCase):

    def test_get_balance(self):
        mcard_entry = SchemeAccountEntryFactory()
        mcard = mcard_entry.scheme_account
        mcard.get_midas_balance([1,2,3])
