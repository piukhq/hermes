from django.test import TestCase

from user.authentication import JwtAuthentication


class TestAuthentication(TestCase):
    @staticmethod
    def get_request(token, *args):
        class MockRequest:
            META = {
                'HTTP_AUTHORIZATION': token
            }
        return MockRequest(*args)

    def test_get_valid_token(self):
        test_token = 'Token blahblahblah-test-token'
        j = JwtAuthentication()
        request = self.get_request(test_token)
        token = j.get_token(request)

        self.assertEqual(test_token[6:], token)

    def test_get_valid_token_type(self):
        test_token = 'Token blahblahblah-test-token'
        j = JwtAuthentication()
        request = self.get_request(test_token)
        token, token_type = j.get_token_type(request)

        self.assertEqual(test_token[6:], token)
        self.assertEqual(token_type, b'token')
