import arrow
import jwt
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.test import Client

from history.utils import GlobalMockAPITestCase
from user.models import CustomUser, ClientApplication, valid_reset_code
from user.tests.factories import UserFactory


class TestResetPassword(GlobalMockAPITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = UserFactory()

    def test_reset_token(self):
        client = Client()
        response = client.post('/users/forgotten_password', data={'email': self.user.email})
        self.assertEqual(response.status_code, 200)

        user_instance = CustomUser.objects.get(email=self.user.email)
        self.assertNotEqual(user_instance.reset_token, None)

        response = client.post('/users/validate_reset_token', data={'token': user_instance.reset_token})
        self.assertEqual(response.status_code, 200)

    def test_reset_with_client_id_duplicate_email(self):
        client = Client()
        app = ClientApplication.objects.create(name='Test', organisation_id=1)
        app_user = CustomUser.objects.create_user(email=self.user.email, client_id=app.client_id)
        response = client.post('/users/forgotten_password', data={
            'email': self.user.email,
            'client_id': app.client_id,
        })
        self.assertEqual(response.status_code, 200)

        bink_app_id = ClientApplication.get_bink_app().client_id
        bink_user = CustomUser.objects.get(email=self.user.email, client_id=bink_app_id)
        app_user = CustomUser.objects.get(email=self.user.email, client_id=app.client_id)
        self.assertIsNone(bink_user.reset_token)
        self.assertIsNotNone(app_user.reset_token)

    def test_reset_token_expiry(self):
        expiry_date = arrow.utcnow()
        expiry_date.shift(hours=-1)
        payload = {
            'email': self.user.email,
            'expiry_date': expiry_date.timestamp
        }
        reset_token = jwt.encode(payload, self.user.client.secret)
        self.user.reset_token = reset_token
        self.user.save()
        token_is_valid = valid_reset_code(reset_token)
        self.assertEqual(token_is_valid, False)


class TestValidatePassword(GlobalMockAPITestCase):
    def test_password_too_short(self):
        expected_messages = ['This password is too short. It must contain at least 8 characters.']
        self.assertRaisesMessage(ValidationError, str(expected_messages), validate_password, password='aBc4')

    def test_password_has_no_numeric(self):
        expected_messages = ['This password is invalid. It must contain a numeric character.']
        self.assertRaisesMessage(ValidationError,
                                 str(expected_messages),
                                 validate_password,
                                 password='aBcDefgh')

    def test_password_has_no_upper_case_character(self):
        expected_messages = ['This password is invalid. It must contain an upper case character.']
        self.assertRaisesMessage(ValidationError,
                                 str(expected_messages),
                                 validate_password,
                                 password='a1cdefgh')

    def test_password_has_no_lower_case_character(self):
        expected_messages = ['This password is invalid. It must contain a lower case character.']
        self.assertRaisesMessage(ValidationError,
                                 str(expected_messages),
                                 validate_password,
                                 password='A123456789')

    def test_validate_message(self):
        expected_messages = ['This password is too short. It must contain at least 8 characters.',
                             'This password is invalid. It must contain a numeric character.',
                             'This password is invalid. It must contain an upper case character.']
        self.assertRaisesMessage(ValidationError, str(expected_messages), validate_password, password='abc')
