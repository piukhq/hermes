import arrow
import jwt
from django.test import Client, TestCase
from hermes import settings
from user.models import CustomUser, valid_reset_code
from user.tests.factories import UserFactory


class TestResetPassword(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.user = UserFactory()
        super().setUpClass()

    def test_reset_token(self):
        client = Client()
        response = client.post('/users/forgotten_password', data={'email': self.user.email})
        self.assertEqual(response.status_code, 200)

        user_instance = CustomUser.objects.get(email=self.user.email)
        self.assertNotEqual(user_instance.reset_token, None)

        response = client.post('/users/validate_reset_token', data={'token': user_instance.reset_token})
        self.assertEqual(response.status_code, 200)

    def test_reset_password(self):
        client = Client()
        self.user.generate_reset_token()
        response = client.post('/users/reset_password', data={'token': self.user.reset_token.decode("utf-8"),
                                                              'password': '1234'})
        self.assertEqual(response.status_code, 200)
        user_instance = CustomUser.objects.get(email=self.user.email)
        self.assertEqual(user_instance.check_password('1234'), True)

    def test_rest_token_expiry(self):
        expiry_date = arrow.utcnow()
        expiry_date.replace(hours=-1)
        payload = {
            'email': 'ak@loyaltyangels.com',
            'expiry_date': expiry_date.timestamp
        }
        reset_token = jwt.encode(payload, settings.TOKEN_SECRET)
        self.user.reset_token = reset_token
        self.user.save()
        token_is_valid = valid_reset_code(reset_token)
        self.assertEqual(token_is_valid, False)
