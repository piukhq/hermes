import arrow
from rest_framework.test import APITestCase

from ubiquity.tests.property_token import GenerateJWToken
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
