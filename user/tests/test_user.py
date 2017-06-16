import json
import time
import arrow
import httpretty as httpretty
from requests_oauthlib import OAuth1Session
from rest_framework.utils.serializer_helpers import ReturnList
from rest_framework.test import APITestCase

from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.test import Client, TestCase

from user.models import (CustomUser, MarketingCode, Referral, hash_ids, valid_promo_code, UserSetting, Setting,
                         ClientApplication, ClientApplicationBundle, ClientApplicationKit)
from user.tests.factories import (UserFactory, UserProfileFactory, fake, SettingFactory, UserSettingFactory,
                                  MarketingCodeFactory)
from unittest import mock

from user.views import facebook_login, twitter_login, social_login
from hermes import settings


BINK_CLIENT_ID = 'MKd3FfDGBi1CIUQwtahmPap64lneCa2R6GvVWKg6dNg4w9Jnpd'
BINK_BUNDLE_ID = 'com.bink.wallet'


class TestRegisterNewUserViews(TestCase):
    def test_register(self):
        client = Client()
        response = client.post(reverse('register_user'), {'email': 'test_1@example.com', 'password': 'Password1'})
        content = json.loads(response.content.decode())
        self.assertEqual(response.status_code, 201)
        self.assertIn('email', content.keys())
        self.assertIn('api_key', content.keys())
        self.assertEqual(content['email'], 'test_1@example.com')

    def test_register_bink_client_and_bundle(self):
        client = Client()
        email = 'test_1@example.com'
        data = {
            'email': email,
            'password': 'Password1',
            'client_id': BINK_CLIENT_ID,
            'bundle_id': BINK_BUNDLE_ID,
        }

        response = client.post(reverse('new_register_user'), data)
        content = json.loads(response.content.decode())
        self.assertEqual(response.status_code, 201)
        self.assertIn('email', content.keys())
        self.assertIn('api_key', content.keys())
        self.assertEqual(content['email'], email)
        user = CustomUser.objects.get(email=email)
        self.assertEqual(user.client_id, BINK_CLIENT_ID)

    def test_register_new_client_and_bundle(self):
        client = Client()
        app = ClientApplication.objects.create(name='Test', organisation_id=1)
        ClientApplicationBundle.objects.create(client_id=app.client_id, bundle_id='com.bink.test')
        email = 'test_1@example.com'
        data = {
            'email': email,
            'password': 'Password1',
            'client_id': app.client_id,
            'bundle_id': 'com.bink.test',
        }

        response = client.post(reverse('new_register_user'), data)
        content = json.loads(response.content.decode())
        self.assertEqual(response.status_code, 201)
        self.assertIn('email', content.keys())
        self.assertIn('api_key', content.keys())
        self.assertEqual(content['email'], email)
        user = CustomUser.objects.get(email=email)
        self.assertEqual(user.client_id, app.client_id)

    def test_register_new_client_same_email(self):
        client = Client()
        app = ClientApplication.objects.create(name='Test', organisation_id=1)
        ClientApplicationBundle.objects.create(client_id=app.client_id, bundle_id='com.bink.test')
        email = 'test_1@example.com'
        data = {
            'email': email,
            'password': 'Password1',
            'client_id': BINK_CLIENT_ID,
            'bundle_id': BINK_BUNDLE_ID,
        }

        response = client.post(reverse('new_register_user'), data)
        self.assertEqual(response.status_code, 201)

        data = {
            'email': email,
            'password': 'Password1',
            'client_id': app.client_id,
            'bundle_id': 'com.bink.test',
        }

        response = client.post(reverse('new_register_user'), data)
        self.assertEqual(response.status_code, 201)

    def test_register_fail_invalid_client_id(self):
        client = Client()
        data = {
            'email': 'test_1@example.com',
            'password': 'Password1',
            'client_id': 'foo',
            'bundle_id': BINK_BUNDLE_ID,
        }

        response = client.post(reverse('new_register_user'), data)
        self.assertEqual(response.status_code, 403)

    def test_register_fail_invalid_bundle(self):
        client = Client()
        data = {
            'email': 'test_1@example.com',
            'password': 'Password1',
            'client_id': BINK_CLIENT_ID,
            'bundle_id': 'foo',
        }

        response = client.post(reverse('new_register_user'), data)
        content = json.loads(response.content.decode())
        self.assertEqual(response.status_code, 403)
        self.assertEqual(content['message'], 'Registration failed.')

    def test_register_fail_email_not_unique(self):
        client = Client()
        data = {
            'email': 'test_1@example.com',
            'password': 'Password1',
        }

        register_url = reverse('register_user')
        response = client.post(register_url, data)
        self.assertEqual(response.status_code, 201)
        response = client.post(register_url, data)
        self.assertEqual(response.status_code, 403)

    def test_uid_is_unique(self):
        client = Client()
        response = client.post(reverse('register_user'), {'email': 'test_2@example.com', 'password': 'Password2'})
        self.assertEqual(response.status_code, 201)
        content = json.loads(response.content.decode())
        uid_1 = content['api_key']

        response = client.post(reverse('register_user'), {'email': 'test_3@example.com', 'password': 'Password3'})
        self.assertEqual(response.status_code, 201)
        content = json.loads(response.content.decode())
        uid_2 = content['api_key']

        self.assertNotEqual(uid_1, uid_2)

    def test_invalid_email(self):
        client = Client()
        response = client.post(reverse('register_user'), {'email': 'test_4@example', 'password': 'Password4'})
        content = json.loads(response.content.decode())
        self.assertEqual(response.status_code, 403)
        self.assertEqual(content['name'], 'REGISTRATION_FAILED')
        self.assertEqual(content['message'], 'Registration failed.')

    def test_no_email(self):
        client = Client()
        response = client.post(reverse('register_user'), {'password': 'Password5', 'promo_code': ''})
        content = json.loads(response.content.decode())
        self.assertEqual(response.status_code, 403)
        self.assertEqual(content['name'], 'REGISTRATION_FAILED')
        self.assertEqual(content['message'], 'Registration failed.')

        response = client.post(reverse('register_user'), {'email': '', 'password': 'Password5'})
        content = json.loads(response.content.decode())
        self.assertEqual(response.status_code, 403)
        self.assertEqual(content['name'], 'REGISTRATION_FAILED')
        self.assertEqual(content['message'], 'Registration failed.')

    def test_no_password(self):
        client = Client()
        response = client.post(reverse('register_user'), {'email': 'test_5@example.com'})
        content = json.loads(response.content.decode())
        self.assertEqual(response.status_code, 403)
        self.assertEqual(content['name'], 'REGISTRATION_FAILED')
        self.assertEqual(content['message'], 'Registration failed.')

        response = client.post(reverse('register_user'), {'email': 'test_5@example.com', 'password': ''})
        content = json.loads(response.content.decode())
        self.assertEqual(response.status_code, 403)
        self.assertEqual(content['name'], 'REGISTRATION_FAILED')
        self.assertEqual(content['message'], 'Registration failed.')

    def test_no_email_and_no_password(self):
        client = Client()
        response = client.post(reverse('register_user'))
        content = json.loads(response.content.decode())
        self.assertEqual(response.status_code, 403)
        self.assertEqual(content['name'], 'REGISTRATION_FAILED')
        self.assertEqual(content['message'], 'Registration failed.')

    def test_good_promo_code(self):
        client = Client()
        # Register a user
        response = client.post(reverse('register_user'), {'email': 'test_6@Example.com', 'password': 'Password6'})
        self.assertEqual(response.status_code, 201)
        # get the corresponding promo code for that user
        u = CustomUser.objects.all().filter(email='test_6@example.com')
        rc = u[0].referral_code
        # Apply the promo code for that user with a new user registration
        response = client.post(
            reverse('register_user'),
            {'email': 'oe42@example.com', 'password': 'Asdfpass10', 'promo_code': rc})
        self.assertEqual(response.status_code, 201)

    def test_good_marketing_code(self):
        client = Client()
        # create a marketing code
        mc = MarketingCode()
        code = "SALE123".lower()
        mc.code = code
        mc.date_from = arrow.utcnow().datetime
        mc.date_to = arrow.utcnow().replace(hours=+12).datetime
        mc.description = ''
        mc.partner = 'Dixons Travel'
        mc.save()

        # Apply the marketing code for this user with a new user registration
        response = client.post(
            reverse('register_user'),
            {'email': 'oe42@example.com', 'password': 'Asdfpass10', 'promo_code': code})
        self.assertEqual(response.status_code, 201)

    def test_existing_email(self):
        client = Client()
        response = client.post(reverse('register_user'), {'email': 'test_6@Example.com', 'password': 'Password6'})
        self.assertEqual(response.status_code, 201)
        response = client.post(reverse('register_user'), {'email': 'test_6@Example.com', 'password': 'Password6'})
        content = json.loads(response.content.decode())
        self.assertEqual(response.status_code, 403)
        self.assertEqual(content['name'], 'REGISTRATION_FAILED')
        self.assertEqual(content['message'], 'Registration failed.')

    def test_existing_email_switch_case(self):
        client = Client()
        response = client.post(reverse('register_user'), {'email': 'test_6@Example.com', 'password': 'Password6'})
        self.assertEqual(response.status_code, 201)
        response = client.post(reverse('register_user'), {'email': 'TeSt_6@Example.com', 'password': 'Password6'})
        content = json.loads(response.content.decode())
        self.assertEqual(response.status_code, 403)
        self.assertEqual(content['name'], 'REGISTRATION_FAILED')
        self.assertEqual(content['message'], 'Registration failed.')

    def test_strange_email_case(self):
        email = 'TEST_12@Example.com'
        response = self.client.post(reverse('register_user'), {'email': email, 'password': 'Password6'})
        content = json.loads(response.content.decode())
        user = CustomUser.objects.get(email=content['email'])
        # Test that django lowers the domain of the email address
        self.assertEqual(user.email, 'TEST_12@example.com')
        # Test that we can login with the domain still with upper case letters
        response = self.client.post(reverse('login'), data={"email": email, "password": 'Password6'})
        self.assertEqual(response.status_code, 200)
        self.assertIn("api_key", response.data)


class TestUserProfileViews(TestCase):
    def test_empty_profile(self):
        user = UserFactory()
        client = Client()
        auth_headers = {
            'HTTP_AUTHORIZATION': 'Token ' + user.create_token()
        }
        response = client.get('/users/me', content_type='application/json', **auth_headers)
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content.decode())
        self.assertEqual(content['email'], user.email)
        self.assertEqual(content['first_name'], None)
        self.assertEqual(content['last_name'], None)
        self.assertEqual(content['date_of_birth'], None)
        self.assertEqual(content['phone'], None)
        self.assertEqual(content['address_line_1'], None)
        self.assertEqual(content['address_line_2'], None)
        self.assertEqual(content['city'], None)
        self.assertEqual(content['region'], None)
        self.assertEqual(content['postcode'], None)
        self.assertEqual(content['country'], None)
        self.assertEqual(content['notifications'], None)
        self.assertEqual(content['pass_code'], None)
        self.assertEqual(content['referral_code'], user.referral_code)

    def test_full_update(self):
        # Create User
        client = Client()
        email = 'user_profile@example.com'
        response = client.post(reverse('register_user'), {'email': email, 'password': 'Password1'})
        self.assertEqual(response.status_code, 201)

        api_key = response.data['api_key']
        auth_headers = {
            'HTTP_AUTHORIZATION': 'Token {0}'.format(api_key)
        }
        data = {
            'email': 'user_profile2@example.com',
            'first_name': 'Andrew',
            'last_name': 'Kenyon',
            'date_of_birth': '1987-12-07',
            'phone': '123456789',
            'address_line_1': '77 Raglan Road',
            'address_line_2': 'Knaphill',
            'city': 'Woking',
            'region': 'Surrey',
            'postcode': 'GU21 2AR',
            'country': 'United Kingdom',
            'notifications': '0',
            'pass_code': '1234',
        }
        response = client.put('/users/me', json.dumps(data),
                              content_type='application/json', **auth_headers)
        self.assertEqual(response.status_code, 200)
        data['uid'] = api_key
        # TODO: SORT THESE
        data['notifications'] = 0
        # TODO: Check all fields in response
        pass
        # TODO: Check all fields in model

    def test_partial_update(self):
        user_profile = UserProfileFactory()
        uid = user_profile.user.uid
        data = {
            'address_line_1': user_profile.address_line_1,
            'address_line_2': user_profile.address_line_2,
            'city': user_profile.city,
            'region': user_profile.region,
            'postcode': user_profile.postcode,
            'country': user_profile.country,
            'gender': user_profile.gender
        }
        auth_headers = {
            'HTTP_AUTHORIZATION': 'Token ' + user_profile.user.create_token()
        }
        client = Client()
        response = client.put('/users/me', json.dumps(data), content_type='application/json', **auth_headers)
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content.decode())
        self.assertEqual(content['uid'], str(uid))
        self.assertEqual(content['email'], user_profile.user.email)
        self.assertEqual(content['first_name'], None)
        self.assertEqual(content['last_name'], None)
        self.assertEqual(content['date_of_birth'], None)
        self.assertEqual(content['phone'], None)
        self.assertEqual(content['address_line_1'], user_profile.address_line_1)
        self.assertEqual(content['address_line_2'], user_profile.address_line_2)
        self.assertEqual(content['city'], user_profile.city)
        self.assertEqual(content['region'],  user_profile.region)
        self.assertEqual(content['postcode'], user_profile.postcode)
        self.assertEqual(content['country'], user_profile.country)
        self.assertEqual(content['notifications'], None)
        self.assertEqual(content['pass_code'], None)
        self.assertEqual(content['gender'], user_profile.gender)

        # Test that adding a new field does not blank existing fields
        data = {
            'phone': user_profile.phone,
        }
        auth_headers = {
            'HTTP_AUTHORIZATION': 'Token ' + user_profile.user.create_token()
        }
        response = client.put('/users/me', json.dumps(data), content_type='application/json', **auth_headers)
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content.decode())
        self.assertEqual(content['uid'], str(uid))
        self.assertEqual(content['email'], user_profile.user.email)
        self.assertEqual(content['first_name'], None)
        self.assertEqual(content['last_name'], None)
        self.assertEqual(content['date_of_birth'], None)
        self.assertEqual(content['phone'], user_profile.phone)
        self.assertEqual(content['address_line_1'], user_profile.address_line_1)
        self.assertEqual(content['address_line_2'], user_profile.address_line_2)
        self.assertEqual(content['city'], user_profile.city)
        self.assertEqual(content['region'],  user_profile.region)
        self.assertEqual(content['postcode'], user_profile.postcode)
        self.assertEqual(content['country'], user_profile.country)
        self.assertEqual(content['notifications'], None)
        self.assertEqual(content['pass_code'], None)

        new_address_1 = fake.street_address()
        data = {
            'address_line_1': new_address_1,
        }
        auth_headers = {
            'HTTP_AUTHORIZATION': 'Token ' + user_profile.user.create_token()
        }
        response = client.put('/users/me', json.dumps(data), content_type='application/json', **auth_headers)
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content.decode())
        self.assertEqual(content['uid'], str(uid))
        self.assertEqual(content['email'], user_profile.user.email)
        self.assertEqual(content['first_name'], None)
        self.assertEqual(content['last_name'], None)
        self.assertEqual(content['date_of_birth'], None)
        self.assertEqual(content['phone'], user_profile.phone)
        self.assertEqual(content['address_line_1'], new_address_1)
        self.assertEqual(content['address_line_2'], user_profile.address_line_2)
        self.assertEqual(content['city'], user_profile.city)
        self.assertEqual(content['region'],  user_profile.region)
        self.assertEqual(content['postcode'], user_profile.postcode)
        self.assertEqual(content['country'], user_profile.country)
        self.assertEqual(content['notifications'], None)
        self.assertEqual(content['pass_code'], None)

    def test_edit_email(self):
        user_profile = UserProfileFactory()
        uid = user_profile.user.uid
        new_email = fake.email()
        data = {
            'email': new_email,
        }
        auth_headers = {
            'HTTP_AUTHORIZATION': 'Token ' + user_profile.user.create_token()
        }
        client = Client()
        response = client.put('/users/me', json.dumps(data), content_type='application/json', **auth_headers)
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content.decode())
        self.assertEqual(content['uid'], str(uid))
        self.assertEqual(content['email'], new_email)

    def test_edit_unique_email(self):
        user_profile1 = UserProfileFactory()
        user_profile2 = UserProfileFactory()
        data = {
            'email': user_profile2.user.email,
        }
        auth_headers = {
            'HTTP_AUTHORIZATION': 'Token ' + user_profile1.user.create_token()
        }
        client = Client()
        response = client.put('/users/me', json.dumps(data), content_type='application/json', **auth_headers)
        self.assertEqual(response.status_code, 400)
        content = json.loads(response.content.decode())
        self.assertEqual(content['email'], ['This field must be unique.'])

    def test_cannot_edit_uid(self):
        # You cannot edit uid, but if you try you still get a 200.
        user_profile = UserProfileFactory()
        uid = user_profile.user.uid
        data = {
            'uid': '172b7aaf-8233-4be3-a50e-67b9c03a5a91',
        }
        auth_headers = {
            'HTTP_AUTHORIZATION': 'Token ' + user_profile.user.create_token()
        }
        client = Client()
        response = client.put('/users/me', json.dumps(data), content_type='application/json', **auth_headers)
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content.decode())
        self.assertEqual(content['uid'], str(uid))

    def test_remove_all(self):
        user_profile = UserProfileFactory()
        uid = user_profile.user.uid
        auth_headers = {
            'HTTP_AUTHORIZATION': 'Token ' + user_profile.user.create_token(),
        }
        client = Client()
        data = {
            'email': user_profile.user.email,
            'first_name': user_profile.first_name,
            'last_name': user_profile.last_name,
            'date_of_birth': user_profile.date_of_birth,
            'phone': user_profile.phone,
            'address_line_1': user_profile.address_line_1,
            'address_line_2': user_profile.address_line_2,
            'city': user_profile.city,
            'region': user_profile.region,
            'postcode': user_profile.postcode,
            'country': user_profile.country,
            'notifications': user_profile.notifications,
            'pass_code': user_profile.pass_code,
            'currency': user_profile.currency
        }

        response = client.put('/users/me', json.dumps(data),
                              content_type='application/json', **auth_headers)
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content.decode())
        self.assertEqual(content['uid'], str(uid))
        self.assertEqual(content['email'], user_profile.user.email)
        self.assertEqual(content['first_name'], user_profile.first_name)
        self.assertEqual(content['last_name'], user_profile.last_name)
        self.assertEqual(content['date_of_birth'], user_profile.date_of_birth)
        self.assertEqual(content['phone'], user_profile.phone)
        self.assertEqual(content['address_line_1'], user_profile.address_line_1)
        self.assertEqual(content['address_line_2'], user_profile.address_line_2)
        self.assertEqual(content['city'], user_profile.city)
        self.assertEqual(content['region'],  user_profile.region)
        self.assertEqual(content['postcode'], user_profile.postcode)
        self.assertEqual(content['country'], user_profile.country)
        self.assertEqual(content['notifications'], 0)
        self.assertEqual(content['pass_code'], user_profile.pass_code)

        data = {
            'email': user_profile.user.email,
            'first_name': '',
            'last_name': '',
            'date_of_birth': None,
            'phone': '',
            'address_line_1': '',
            'address_line_2': '',
            'city': '',
            'region': '',
            'postcode': '',
            'country': '',
            'notifications': None,
            'pass_code': '',
        }
        response = client.put('/users/me', json.dumps(data), content_type='application/json', **auth_headers)
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content.decode())
        self.assertEqual(content['uid'], str(uid))
        self.assertEqual(content['email'], user_profile.user.email)
        self.assertEqual(content['first_name'], '')
        self.assertEqual(content['last_name'], '')
        self.assertEqual(content['date_of_birth'], None)
        self.assertEqual(content['phone'], '')
        self.assertEqual(content['address_line_1'], '')
        self.assertEqual(content['address_line_2'], '')
        self.assertEqual(content['city'], '')
        self.assertEqual(content['region'],  '')
        self.assertEqual(content['postcode'], '')
        self.assertEqual(content['country'], '')
        self.assertEqual(content['notifications'], None)
        self.assertEqual(content['pass_code'], '')


class TestAuthenticationViews(APITestCase):
    @classmethod
    def setUpClass(cls):
        cls.user = UserFactory()
        super().setUpClass()

        cls.auth_service_headers = {'HTTP_AUTHORIZATION': 'Token ' + settings.SERVICE_API_KEY}

    def test_local_login_valid(self):
        data = {
            "email": self.user.email,
            "password": 'defaultpassword'
        }
        response = self.client.post(reverse('login'), data=data)

        self.assertEqual(response.status_code, 200)
        self.assertIn("api_key", response.data)

    def test_local_login_invalid(self):
        data = {
            "email": self.user.email,
            "password": 'badpassword'
        }
        response = self.client.post(reverse('login'), data=data)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["message"], 'Login credentials incorrect.')

    def test_local_login_disable(self):
        self.user.is_active = False
        self.user.save()
        data = {
            "email": self.user.email,
            "password": 'defaultpassword'
        }
        response = self.client.post(reverse('login'), data=data)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["message"], "The account associated with this email address is suspended.")

    def test_login_with_client_and_bundle(self):
        client = Client()
        data = {
            'email': self.user.email,
            'password': 'defaultpassword',
            'client_id': BINK_CLIENT_ID,
            'bundle_id': BINK_BUNDLE_ID,
        }

        response = client.post(reverse('new_login'), data)
        content = json.loads(response.content.decode())
        self.assertEqual(response.status_code, 200)
        self.assertIn('email', content.keys())
        self.assertIn('api_key', content.keys())
        self.assertEqual(content['email'], self.user.email)

    def test_login_duplicate_email_different_client(self):
        client = Client()
        data_1_old = {
            'email': self.user.email,
            'password': 'defaultpassword',
        }
        data_1_new = {
            'email': self.user.email,
            'password': 'defaultpassword',
            'client_id': BINK_CLIENT_ID,
            'bundle_id': BINK_BUNDLE_ID,
        }

        app = ClientApplication.objects.create(name='Test', organisation_id=1)
        other_user = CustomUser.objects.create_user(self.user.email, password='foo', client_id=app.client_id)
        other_bundle = ClientApplicationBundle.objects.create(client=app, bundle_id='com.bink.test')
        data_2 = {
            'email': other_user.email,
            'password': 'foo',
            'client_id': app.client_id,
            'bundle_id': other_bundle.bundle_id,
        }

        response = client.post(reverse('login'), data_1_old)
        self.assertEqual(response.status_code, 200)

        response = client.post(reverse('new_login'), data_1_new)
        self.assertEqual(response.status_code, 200)

        response = client.post(reverse('new_login'), data_2)
        self.assertEqual(response.status_code, 200)

    def test_login_fail_client_invalid_for_user(self):
        client = Client()
        app = ClientApplication.objects.create(name='Test', organisation_id=1)
        user = CustomUser.objects.create_user('new@test.com')
        user.client_id = app.client_id
        user.save()
        data = {
            'email': 'new@test.com',
            'password': 'defaultpassword',
            'client_id': BINK_CLIENT_ID,
            'bundle_id': BINK_BUNDLE_ID,
        }

        response = client.post(reverse('new_login'), data)
        self.assertEqual(response.status_code, 403)

    def test_login_fail_invalid_client_id(self):
        client = Client()
        data = {
            'email': self.user.email,
            'password': 'defaultpassword',
            'client_id': 'foo',
            'bundle_id': BINK_BUNDLE_ID,
        }

        response = client.post(reverse('new_login'), data)
        self.assertEqual(response.status_code, 403)

    def test_login_fail_invalid_bundle(self):
        client = Client()
        data = {
            'email': self.user.email,
            'password': 'defaultpassword',
            'client_id': BINK_CLIENT_ID,
            'bundle_id': 'foo',
        }

        response = client.post(reverse('new_login'), data)
        self.assertEqual(response.status_code, 403)

    def test_remote_authentication_valid(self):
        client = Client()
        auth_headers = {
            'HTTP_AUTHORIZATION': "Token " + self.user.create_token()
        }
        response = client.get('/users/authenticate/', **auth_headers)
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content.decode())
        self.assertEqual(content['id'], str(self.user.id))

    def test_remote_authentication_invalid(self):
        client = Client()
        uid = '7772a731-2d3a-42f2-bb4c-cc7aa7b01fd9'
        auth_headers = {
            'HTTP_AUTHORIZATION': "Token " + str(uid),
        }
        response = client.get('/users/authenticate/', **auth_headers)
        self.assertEqual(response.status_code, 401)
        content = json.loads(response.content.decode())
        self.assertEqual(content['detail'], 'Authentication credentials were not provided.')

    def test_change_password(self):
        auth_headers = {'HTTP_AUTHORIZATION': "Token " + self.user.create_token()}
        response = self.client.put('/users/me/password', {'password': 'Test1234'}, **auth_headers)
        user = CustomUser.objects.get(id=self.user.id)

        self.assertEqual(response.status_code, 200)
        user = authenticate(username=user.email, password='Test1234')
        self.assertTrue(user.password)

    def test_change_password_once(self):
        auth_headers = {'HTTP_AUTHORIZATION': "Token " + self.user.create_token()}
        response = self.client.put('/users/me/password', {'password': 'Test1234'}, **auth_headers)
        user = CustomUser.objects.get(id=self.user.id)

        self.assertEqual(response.status_code, 200)
        user = authenticate(username=user.email, password='Test1234')
        self.assertTrue(user.password)

        token = user.generate_reset_token()

        response = self.client.post('/users/reset_password',
                                    {'password': '1stPassword', "token": token.decode('UTF-8'), },
                                    **self.auth_service_headers)
        user = CustomUser.objects.get(id=self.user.id)

        self.assertEqual(response.status_code, 200)
        user = authenticate(username=user.email, password='1stPassword')

        self.assertTrue(user.password)

        # Now try again to ensure we can't do it twice
        response = self.client.post('/users/reset_password',
                                    {'password': '2ndPassword',
                                     'token': token.decode('UTF-8'), },
                                    **self.auth_service_headers)
        user = CustomUser.objects.get(id=self.user.id)

        self.assertGreaterEqual(response.status_code, 400)
        user = authenticate(username=user.email, password='2ndPassword')
        self.assertFalse(user)

    @mock.patch('user.models.CustomUser.get_expiry_date')
    def test_change_password_once_timeout(self, mock_get_expiry_date):
        mock_get_expiry_date.return_value = arrow.utcnow().replace(seconds=+10)

        auth_headers = {'HTTP_AUTHORIZATION': "Token " + self.user.create_token()}
        response = self.client.put('/users/me/password', {'password': 'Test1234'}, **auth_headers)
        user = CustomUser.objects.get(id=self.user.id)

        self.assertEqual(response.status_code, 200)
        user = authenticate(username=user.email, password='Test1234')
        self.assertTrue(user.password)

        token = user.generate_reset_token()

        time.sleep(12)

        response = self.client.post('/users/reset_password',
                                    {'password': '1stPassword', "token": token.decode('UTF-8'), },
                                    **self.auth_service_headers)
        user = CustomUser.objects.get(id=self.user.id)

        self.assertGreaterEqual(response.status_code, 400)
        user = authenticate(username=user.email, password='1stPassword')
        self.assertFalse(user)


class TestTwitterLogin(APITestCase):
    @mock.patch('user.views.twitter_login', autospec=True)
    @mock.patch.object(OAuth1Session, 'fetch_access_token', autospec=True)
    def test_twitter_login_web(self, mock_fetch_access_token, mock_twitter_login):
        mock_twitter_login.return_value = HttpResponse()
        mock_fetch_access_token.return_value = {'oauth_token': 'sdfsdf', 'oauth_token_secret': 'asdfasdf'}
        self.client.post('/users/auth/twitter_web', {"oauth_token": 'G9E511MOEQ', "oauth_verifier": '1234'})
        self.assertEqual(mock_fetch_access_token.call_args[0][1],  'https://api.twitter.com/oauth/access_token')
        self.assertEqual(mock_twitter_login.call_args[0], ('sdfsdf', 'asdfasdf'))

    @mock.patch.object(OAuth1Session, 'fetch_request_token', autospec=True)
    def test_twitter_request_token(self, mock_fetch_request_token):
        mock_fetch_request_token.return_value = {'test': True}
        response = self.client.post('/users/auth/twitter_web')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {'test': True})
        self.assertEqual(mock_fetch_request_token.call_args[0][1],  'https://api.twitter.com/oauth/request_token')

    @mock.patch('user.views.twitter_login', autospec=True)
    def test_twitter_login_app(self, twitter_login_mock):
        twitter_login_mock.return_value = HttpResponse()
        self.client.post('/users/auth/twitter', {'access_token': '23452345', 'access_token_secret': '235489234'})
        self.assertEqual(twitter_login_mock.call_args[0], ('23452345', '235489234'))

    @mock.patch('user.views.social_login', autospec=True)
    @httpretty.activate
    def test_twitter_login(self, mock_social_login):
        twitter_id = 'omsr4k7yta'
        user = UserFactory(twitter=twitter_id)
        mock_social_login.return_value = (201, user)
        httpretty.register_uri(httpretty.GET, 'https://api.twitter.com/1.1/account/verify_credentials.json',
                               body=json.dumps({'id_str': twitter_id}), content_type="application/json")
        response = twitter_login("V7UoKuG529N3L92386ZdF0TE2kUGnzAp", "2ghMHZux2o02Xd47X7hsP6UH897fDmBb")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['email'], user.email)


class TestFacebookLogin(APITestCase):
    @mock.patch('user.views.facebook_login', autospec=True)
    @httpretty.activate
    def test_facebook_web_login_view(self, facebook_login_mock):
        facebook_login_mock.return_value = HttpResponse()
        httpretty.register_uri(httpretty.GET, 'https://graph.facebook.com/v2.3/oauth/access_token',
                               body=json.dumps({'access_token': '252345'}), content_type="application/json")
        response = self.client.post('/users/auth/facebook_web', data={'clientId': '6b045AG',
                                                                      'redirectUri': 'pa11mZTFOB', 'code': '235345wer'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(facebook_login_mock.call_args[0][0],  '252345')

    @mock.patch('user.views.facebook_login', autospec=True)
    @httpretty.activate
    def test_facebook_login_view(self, mock_facebook_login):
        mock_facebook_login.return_value = HttpResponse()
        httpretty.register_uri(httpretty.GET, 'https://graph.facebook.com/me',
                               body=json.dumps({'id': '12'}), content_type="application/json")
        response = self.client.post('/users/auth/facebook', data={'access_token': '25232345', 'user_id': '12'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_facebook_login.call_args[0][0],  '25232345')

    @httpretty.activate
    def test_facebook_login_view_bad_id(self):
        httpretty.register_uri(httpretty.GET, 'https://graph.facebook.com/me',
                               body=json.dumps({'id': '1122'}), content_type="application/json")
        response = self.client.post('/users/auth/facebook', data={'access_token': '25232345', 'user_id': '12'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data['message'], 'user_id is invalid for given access token')
        self.assertEqual(response.data['name'], 'FACEBOOK_INVALID_USER')
        self.assertEqual(response.data['code'], 403)

    @mock.patch('user.views.social_login', autospec=True)
    @httpretty.activate
    def test_facebook_login(self, mock_social_login):
        facebook_id = 'O7bz6vG60Y'
        user = UserFactory(facebook=facebook_id)
        mock_social_login.return_value = (200, user)
        httpretty.register_uri(httpretty.GET, 'https://graph.facebook.com/v2.3/me',
                               body=json.dumps({"email": "", "id": facebook_id}), content_type="application/json")
        response = facebook_login('Ju76xER1A5')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['email'], user.email)


class TestSocialLogin(APITestCase):
    def test_social_login_exists(self):
        facebook_id = 'O7bz6vG60Y'
        created_user = UserFactory(facebook=facebook_id)
        status, user = social_login(facebook_id, None, 'facebook')
        self.assertEqual(status, 200)
        self.assertEqual(created_user, user)

    def test_social_login_exists_no_email(self):
        facebook_id = 'O7bz6vG60Y'
        UserFactory(facebook=facebook_id, email=None)
        status, user = social_login(facebook_id, 'frank@sea.com', 'facebook')
        self.assertEqual(status, 200)
        self.assertEqual(user.email, 'frank@sea.com')

    def test_social_login_not_linked(self):
        user = UserFactory()
        twitter_id = '3456bz23466vG'
        status, user = social_login(twitter_id, user.email, 'twitter')
        self.assertEqual(status, 200)
        self.assertEqual(user.twitter, twitter_id)

    def test_social_login_no_user(self):
        twitter_id = '6u111bzUNL'
        twitter_email = 'bob@sea.com'
        status, user = social_login(twitter_id, twitter_email, 'twitter')
        self.assertEqual(status, 201)
        self.assertEqual(user.twitter, twitter_id)
        self.assertEqual(user.email, twitter_email)

    def test_social_login_no_user_no_email(self):
        twitter_id = 'twitter_email'
        status, user = social_login(twitter_id, None, 'twitter')
        self.assertEqual(status, 201)
        self.assertEqual(user.twitter, twitter_id)
        self.assertEqual(user.email, None)


class TestUserModel(TestCase):
    def test_create_referral(self):
        user = UserFactory()
        user_2 = UserFactory()
        user_2.create_referral(user.referral_code)
        self.assertTrue(Referral.objects.filter(referrer=user, recipient=user_2).exists())

    def test_valid_promo_code(self):
        user = UserFactory()
        self.assertTrue(valid_promo_code(hash_ids.encode(user.id)))

    def test_valid_promo_code_bad(self):
        self.assertFalse(valid_promo_code(''))
        self.assertFalse(valid_promo_code(None))
        self.assertFalse(valid_promo_code(3457987))


class TestCustomUserManager(TestCase):
    def test_create_user(self):
        password = '234'
        user = CustomUser.objects._create_user('test@sdf.com', password, is_staff=False, is_superuser=False)
        self.assertNotEqual(user.password, password)


class TestSettings(APITestCase):
    @classmethod
    def setUpClass(cls):
        user = UserFactory()
        cls.auth_headers = {'HTTP_AUTHORIZATION': 'Token ' + user.create_token()}
        super().setUpClass()

    def test_list_settings(self):
        SettingFactory()
        SettingFactory()
        resp = self.client.get('/users/settings/', **self.auth_headers)

        self.assertEqual(resp.status_code, 200, )
        self.assertEqual(type(resp.data), ReturnList)
        self.assertEqual(len(resp.data), 2)
        self.assertIn('slug', resp.data[0])
        self.assertIn('value_type', resp.data[0])
        self.assertIn('default_value', resp.data[0])
        self.assertIn('scheme', resp.data[0])
        self.assertIn('label', resp.data[0])
        self.assertIn('category', resp.data[0])

    def test_validate_setting(self):
        s = Setting(slug='test-setting', value_type=Setting.BOOLEAN, default_value='true')
        with self.assertRaises(ValidationError) as e:
            s.full_clean()

        self.assertEqual(e.exception.messages, ["'true' is not a valid value for type boolean."])


class TestUserSettings(APITestCase):
    @classmethod
    def setUpClass(cls):
        cls.user = UserFactory()
        cls.auth_headers = {'HTTP_AUTHORIZATION': 'Token ' + cls.user.create_token()}
        super().setUpClass()

    def test_list_user_settings(self):
        setting = SettingFactory(category=Setting.MARKETING)
        UserSettingFactory(user=self.user, value='1', setting=setting)

        SettingFactory()

        resp = self.client.get('/users/me/settings', **self.auth_headers)
        data = resp.json()

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]['category'], 'Marketing')
        self.assertEqual(data[0]['default_value'], '0')
        self.assertEqual(data[0]['is_user_defined'], True)
        self.assertEqual(data[0]['label'], None)
        self.assertEqual(data[0]['scheme'], None)
        self.assertEqual(data[0]['slug'], setting.slug)
        self.assertEqual(data[0]['user'], self.user.id)
        self.assertEqual(data[0]['value'], '1')
        self.assertEqual(data[0]['value_type'], setting.value_type_name)

    @mock.patch('intercom.intercom_api.reset_user_settings')
    def test_delete_user_settings(self, mock_update_custom_attribute):
        settings = [SettingFactory(slug='marketing-bink'), SettingFactory()]
        UserSettingFactory(user=self.user, value='1', setting=settings[0])
        UserSettingFactory(user=self.user, value='0', setting=settings[1])

        user_settings = UserSetting.objects.filter(user=self.user)
        self.assertEqual(len(user_settings), 2)

        resp = self.client.delete('/users/me/settings', **self.auth_headers)

        self.assertEqual(resp.status_code, 204)

        user_settings = UserSetting.objects.filter(user=self.user)
        self.assertEqual(len(user_settings), 0)

        self.assertEqual(mock_update_custom_attribute.call_count, 1)

    @mock.patch('intercom.intercom_api.update_user_custom_attribute')
    def test_update_intercom_user_settings(self, mock_update_custom_attribute):
        settings = [SettingFactory(slug='marketing-bink'), SettingFactory(slug='marketing-external')]
        UserSettingFactory(user=self.user, value='1', setting=settings[0])
        UserSettingFactory(user=self.user, value='0', setting=settings[1])

        user_setting = UserSetting.objects.filter(user=self.user, setting__slug=settings[0].slug).first()
        self.assertEqual(user_setting.value, '1')

        user_setting = UserSetting.objects.filter(user=self.user, setting__slug=settings[1].slug).first()
        self.assertEqual(user_setting.value, '0')

        data = {
            settings[0].slug: '0',  # False
            settings[1].slug: '1',  # True
        }
        resp = self.client.put('/users/me/settings', data=data, **self.auth_headers)

        self.assertEqual(resp.status_code, 204)

        user_setting = UserSetting.objects.filter(user=self.user, setting__slug=settings[0].slug).first()
        self.assertEqual(user_setting.value, '0')

        user_setting = UserSetting.objects.filter(user=self.user, setting__slug=settings[1].slug).first()
        self.assertEqual(user_setting.value, '1')

        self.assertEqual(mock_update_custom_attribute.call_count, 2)
        intercom_calls_data = {
            mock_update_custom_attribute.call_args_list[0][0][2]: mock_update_custom_attribute.call_args_list[0][0][3],
            mock_update_custom_attribute.call_args_list[1][0][2]: mock_update_custom_attribute.call_args_list[1][0][3]
        }

        # marketing-bink updated to False in intercom
        self.assertFalse(intercom_calls_data['marketing-bink'])

        # marketing-external updated to True in intercom
        self.assertTrue(intercom_calls_data['marketing-external'])

        self.assertEqual(mock_update_custom_attribute.call_count, len(settings))

    @mock.patch('intercom.intercom_api.update_user_custom_attribute')
    def test_update_non_intercom_user_settings(self, mock_update_custom_attribute):
        settings = [SettingFactory(), SettingFactory()]
        UserSettingFactory(user=self.user, value='1', setting=settings[0])
        UserSettingFactory(user=self.user, value='0', setting=settings[1])

        user_setting = UserSetting.objects.filter(user=self.user, setting__slug=settings[0].slug).first()
        self.assertEqual(user_setting.value, '1')

        user_setting = UserSetting.objects.filter(user=self.user, setting__slug=settings[1].slug).first()
        self.assertEqual(user_setting.value, '0')

        data = {
            settings[0].slug: '0',
            settings[1].slug: '1',
        }
        resp = self.client.put('/users/me/settings', data=data, **self.auth_headers)

        self.assertEqual(resp.status_code, 204)

        user_setting = UserSetting.objects.filter(user=self.user, setting__slug=settings[0].slug).first()
        self.assertEqual(user_setting.value, '0')

        user_setting = UserSetting.objects.filter(user=self.user, setting__slug=settings[1].slug).first()
        self.assertEqual(user_setting.value, '1')

        self.assertFalse(mock_update_custom_attribute.called)

    def test_update_incorrect_user_settings(self):
        setting = SettingFactory()
        data = {
            'bad-slug-1': '5',
            setting.slug: '1',
            'bad-slug-2': 'bad@bad.com',
        }
        resp = self.client.put('/users/me/settings', data=data, **self.auth_headers)
        data = resp.json()

        self.assertEqual(resp.status_code, 400)
        self.assertIn('error', data)
        self.assertIn('messages', data)
        self.assertEqual(data['error'], 'Some of the given settings are invalid.')
        self.assertIn('bad-slug-1', data['messages'])
        self.assertIn('bad-slug-2', data['messages'])
        self.assertNotIn(setting.slug, data['messages'])

    def test_update_user_setting_with_bad_value(self):
        bool_setting = SettingFactory()
        num_setting = SettingFactory(value_type=0)

        data = {
            bool_setting.slug: 'kitten',
            num_setting.slug: 'not even a number',
        }
        resp = self.client.put('/users/me/settings', data=data, **self.auth_headers)
        data = resp.json()

        self.assertEqual(resp.status_code, 400)
        self.assertIn('error', data)
        self.assertIn('messages', data)
        self.assertEqual(data['error'], 'Some of the given settings are invalid.')
        self.assertEqual(len(data['messages']), 2)
        self.assertIn("'kitten' is not a valid value for type boolean.", data['messages'])
        self.assertIn("'not even a number' is not a valid value for type number.", data['messages'])

    @mock.patch('intercom.intercom_api.update_user_custom_attribute')
    def test_create_non_intercom_settings(self, mock_update_custom_attribute):
        setting = SettingFactory()

        data = {
            setting.slug: '1',
        }
        resp = self.client.put('/users/me/settings', data=data, **self.auth_headers)

        self.assertEqual(resp.status_code, 204)

        user_setting = UserSetting.objects.filter(user=self.user, setting__slug=setting.slug).first()
        self.assertEqual(user_setting.value, '1')

        self.assertFalse(mock_update_custom_attribute.called)

    @mock.patch('intercom.intercom_api.update_user_custom_attribute')
    def test_create_intercom_setting(self, mock_update_custom_attribute):
        setting = SettingFactory(slug='marketing-bink')

        data = {
            setting.slug: '1',
        }
        resp = self.client.put('/users/me/settings', data=data, **self.auth_headers)

        self.assertEqual(resp.status_code, 204)

        user_setting = UserSetting.objects.filter(user=self.user, setting__slug=setting.slug).first()
        self.assertEqual(user_setting.value, '1')

        self.assertEqual(mock_update_custom_attribute.call_count, 1)
        # marketing-bink updated to True in intercom
        self.assertEqual(mock_update_custom_attribute.call_args_list[0][0][2], 'marketing-bink')
        self.assertEqual(mock_update_custom_attribute.call_args_list[0][0][3], True)


class TestAppKitIdentification(APITestCase):
    def test_app_kit_known(self):
        data = {
            'client_id': BINK_CLIENT_ID,
            'kit_name': 'core',
        }
        response = self.client.post(reverse('app_kit'), data=data)
        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.data, {})

    def test_app_kit_known_case_insensitive(self):
        data = {
            'client_id': BINK_CLIENT_ID,
            'kit_name': 'Core',
        }
        response = self.client.post(reverse('app_kit'), data=data)
        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.data, {})

    def test_app_kit_invalid(self):
        data = {
            'client_id': BINK_CLIENT_ID,
            'kit_name': 'randomkit',
        }
        response = self.client.post(reverse('app_kit'), data=data)
        self.assertTrue(ClientApplicationKit.objects.filter(**data).exists())
        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.data, {})

    def test_app_kit_invalid_client_id(self):
        data = {
            'client_id': 'foo',
            'kit_name': 'core',
        }
        response = self.client.post(reverse('app_kit'), data=data)
        self.assertFalse(ClientApplicationKit.objects.filter(**data).exists())
        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.data, {})


class TestVerifyToken(APITestCase):
    def test_valid_token(self):
        user = UserFactory()
        token = user.create_token()
        headers = {'HTTP_AUTHORIZATION': 'Token {}'.format(token)}

        response = self.client.get(reverse('verify_token'), **headers)
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data)

    def test_invalid_token(self):
        # sub 30, secret 'foo'
        token = ('eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOjMwLCJpYXQiOjE0OTE1NTU0ODl9.'
                 'xXa36rs6keNVo9YVbFGgWe3EiXnNvS7yJ65fXgYnSLg')
        headers = {'HTTP_AUTHORIZATION': 'Token {}'.format(token)}

        response = self.client.get(reverse('verify_token'), **headers)
        self.assertEqual(response.status_code, 401)


class TestApplyPromoCode(APITestCase):
    def setUp(self):
        self.user1 = UserFactory()
        self.user2 = UserFactory()

        self.marketing_code = MarketingCodeFactory()

        self.auth_headers = {'HTTP_AUTHORIZATION': 'Token {}'.format(self.user1.create_token())}

    def test_valid_marketing_code(self):
        """
        Request to apply `self.marketing_code` to `self.user` and assert that it has been applied correctly.
        """
        resp = self.client.post(reverse('promo_code'),
                                data={'promo_code': self.marketing_code.code},
                                **self.auth_headers)
        self.assertEqual(200, resp.status_code)

        updated_user = CustomUser.objects.get(pk=self.user1.id)
        self.assertEqual(updated_user.marketing_code, self.marketing_code)

    def test_valid_referral_code(self):
        """
        Request to apply the referral code of `self.user2` to `self.user` and assert that the referral has been created.
        """
        resp = self.client.post(reverse('promo_code'),
                                data={'promo_code': self.user2.referral_code},
                                **self.auth_headers)
        self.assertEqual(200, resp.status_code)
        referral = Referral.objects.filter(referrer=self.user2, recipient=self.user1)
        self.assertTrue(referral.exists())

    def test_invalid_code(self):
        """
        Request to apply a made-up code to `self.user1` and assert that no referral or marketing codes have been applied
        to `self.user1`.
        """
        resp = self.client.post(reverse('promo_code'),
                                data={'promo_code': 'm209b87w3bjh0sz7q3vat90agj'},
                                **self.auth_headers)
        self.assertEqual(200, resp.status_code)

        updated_user = CustomUser.objects.get(pk=self.user1.id)
        self.assertIsNone(updated_user.marketing_code)

        referral = Referral.objects.filter(recipient=self.user1)
        self.assertFalse(referral.exists())

    def test_apply_multiple_referrals(self):
        """
        Request to apply the referral code of `self.user2` to `self.user1` and assert that the referral has been
        created. Then, request to apply the referral code of `user3` to `self.user1` and assert that a second referral
        has not been created.
        """
        user3 = UserFactory()

        resp = self.client.post(reverse('promo_code'),
                                data={'promo_code': self.user2.referral_code},
                                **self.auth_headers)
        self.assertEqual(200, resp.status_code)
        referral = Referral.objects.filter(referrer=self.user2, recipient=self.user1)
        self.assertTrue(referral.exists())

        resp = self.client.post(reverse('promo_code'),
                                data={'promo_code': user3.referral_code},
                                **self.auth_headers)
        self.assertEqual(200, resp.status_code)
        referral = Referral.objects.filter(referrer=user3, recipient=self.user1)
        self.assertFalse(referral.exists())


class TestTermsAndConditions(TestCase):
    def setUp(self):
        self.user1 = UserFactory()

        self.auth_headers = {'HTTP_AUTHORIZATION': 'Token {}'.format(self.user1.create_token())}

    def test_terms_and_conditions(self):
        client = Client()
        self.user1.client.organisation.terms_and_conditions = "<p>This is a test</p>"
        self.user1.client.organisation.save()
        response = client.get(reverse('terms_and_conditions'), **self.auth_headers)
        content = json.loads(response.content.decode())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(content['terms_and_conditions'],
                         "<p>This is a test</p>")
