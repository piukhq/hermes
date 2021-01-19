import json
from unittest.mock import patch

import arrow
from rest_framework.test import APITestCase

from django.urls import reverse

from ubiquity.tests.property_token import GenerateJWToken
from user.models import CustomUser
from user.tests.factories import ClientApplicationBundleFactory, OrganisationFactory, ClientApplicationFactory


class TestRegistration(APITestCase):
    @classmethod
    def setUpClass(cls):
        cls.history_patcher = patch('history.signals.record_history', autospec=True)
        cls.history_patcher.start()
        cls.bundle = ClientApplicationBundleFactory()
        cls.token_generator = GenerateJWToken
        super().setUpClass()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.history_patcher.stop()
        super().tearDownClass()

    def test_service_registration(self):
        data = {
            'organisation_id': self.bundle.client.organisation.name,
            'client_secret': self.bundle.client.secret,
            'bundle_id': self.bundle.bundle_id
        }
        token = self.token_generator(**data).get_token()
        auth_headers = {'HTTP_AUTHORIZATION': 'bearer {}'.format(token)}
        consent = json.dumps({
            'consent': {
                'email': 'test@email.bink',
                'timestamp': arrow.utcnow().timestamp
            }
        })

        resp = self.client.post('/ubiquity/service', data=consent, content_type='application/json', **auth_headers)
        self.assertEqual(resp.status_code, 201)

        organisation = OrganisationFactory(name='Test other organisation')
        client = ClientApplicationFactory(name='random other client', organisation=organisation)
        bundle = ClientApplicationBundleFactory(bundle_id='test.other.user', client=client)

        data = {
            'organisation_id': bundle.client.organisation.name,
            'client_secret': bundle.client.secret,
            'bundle_id': bundle.bundle_id
        }
        token = self.token_generator(**data).get_token()
        auth_headers = {'HTTP_AUTHORIZATION': 'bearer {}'.format(token)}
        consent = json.dumps({
            'consent': {
                'email': 'test@email.bink',
                'timestamp': arrow.utcnow().timestamp
            }
        })

        resp = self.client.post('/ubiquity/service', data=consent, content_type='application/json', **auth_headers)
        self.assertEqual(resp.status_code, 201)

    def test_service_registration_with_malformed_data_existing_user(self):
        BINK_CLIENT_ID = 'MKd3FfDGBi1CIUQwtahmPap64lneCa2R6GvVWKg6dNg4w9Jnpd'
        BINK_BUNDLE_ID = 'com.bink.wallet'

        user_response = self.client.post(
            reverse('register_user'),
            {
                'email': 'test_1@example.com',
                'password': 'Password1',
                'client_id': BINK_CLIENT_ID,
                'bundle_id': BINK_BUNDLE_ID
            }
        )

        token = user_response.json()['api_key']
        auth_headers = {'HTTP_AUTHORIZATION': 'token {}'.format(token)}
        consent = json.dumps({
            'consent': {
                'email': user_response.json()['email'],
                'timestamp': "abc"
            }
        })

        resp = self.client.post('/ubiquity/service', data=consent, content_type='application/json', **auth_headers)
        # Check it has not deactivated the user going through this journey.
        user = CustomUser.objects.get(uid=user_response.json()['uid'])

        self.assertEqual(resp.status_code, 400)
        self.assertTrue(user.is_active)

    def test_service_registration_wrong_data(self):
        data = {
            'organisation_id': self.bundle.client.organisation.name,
            'client_secret': self.bundle.client.secret,
            'bundle_id': self.bundle.bundle_id,
        }
        token = self.token_generator(**data).get_token()
        auth_headers = {'HTTP_AUTHORIZATION': 'bearer {}'.format(token)}
        consent = json.dumps({
            'consent': {
                'timestamp': 'not a timestamp',
                'email': 'wrongconsent@bink.test'
            }
        })

        wrong_consent_resp = self.client.post('/ubiquity/service', data=consent, content_type='application/json',
                                              **auth_headers)
        self.assertEqual(wrong_consent_resp.status_code, 400)
        self.assertIn('Malformed request.', wrong_consent_resp.json().get('detail'))

    def test_service_registration_wrong_header(self):
        data = {
            'organisation_id': self.bundle.client.organisation.name,
            'client_secret': self.bundle.client.secret,
            'bundle_id': 'wrong bundle id'
        }
        token = self.token_generator(**data).get_token()
        auth_headers = {'HTTP_AUTHORIZATION': 'bearer {}'.format(token)}
        consent = json.dumps({
            'consent': {
                'timestamp': arrow.utcnow().timestamp
            }
        })

        wrong_header_resp = self.client.post('/ubiquity/service', data=consent, content_type='application/json',
                                             **auth_headers)
        self.assertEqual(wrong_header_resp.status_code, 403)
        self.assertIn('Invalid token', wrong_header_resp.json()['detail'])
