import json

import arrow
from rest_framework.test import APITestCase

from ubiquity.tests.property_token import GenerateJWToken
from user.tests.factories import ClientApplicationBundleFactory, OrganisationFactory, ClientApplicationFactory


class TestRegistration(APITestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = ClientApplicationBundleFactory()
        cls.token_generator = GenerateJWToken
        super().setUpClass()

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
