import json
import httpretty as httpretty
from django.contrib.auth import authenticate
from django.http import HttpResponse
from django.test import Client, TestCase
from requests_oauthlib import OAuth1Session
from user.models import CustomUser
from user.tests.factories import UserFactory, UserProfileFactory, fake
from rest_framework.test import APITestCase
from unittest import mock
from user.views import facebook_graph, twitter_login


class TestRegisterNewUser(TestCase):
    def test_register(self):
        client = Client()
        response = client.post('/users/register/', {'email': 'test_1@example.com', 'password': 'password1'})
        content = json.loads(response.content.decode())
        self.assertEqual(response.status_code, 201)
        self.assertIn('email', content.keys())
        self.assertIn('api_key', content.keys())
        self.assertEqual(content['email'], 'test_1@example.com')

    def test_uid_is_unique(self):
        client = Client()
        response = client.post('/users/register/', {'email': 'test_2@example.com', 'password': 'password2'})
        self.assertEqual(response.status_code, 201)
        content = json.loads(response.content.decode())
        uid_1 = content['api_key']

        response = client.post('/users/register/', {'email': 'test_3@example.com', 'password': 'password3'})
        self.assertEqual(response.status_code, 201)
        content = json.loads(response.content.decode())
        uid_2 = content['api_key']

        self.assertNotEqual(uid_1, uid_2)

    def test_invalid_email(self):
        client = Client()
        response = client.post('/users/register/', {'email': 'test_4@example', 'password': 'password4'})
        self.assertEqual(response.status_code, 400)
        content = json.loads(response.content.decode())
        self.assertEqual(list(content.keys()), ['email'])
        self.assertEqual(content['email'], ['Enter a valid email address.'])

    def test_no_email(self):
        client = Client()
        response = client.post('/users/register/', {'password': 'password'})
        self.assertEqual(response.status_code, 400)
        content = json.loads(response.content.decode())
        self.assertEqual(list(content.keys()), ['email'])
        self.assertEqual(content['email'], ['This field is required.'])

        response = client.post('/users/register/', {'email': '', 'password': 'password'})
        self.assertEqual(response.status_code, 400)
        content = json.loads(response.content.decode())
        self.assertEqual(list(content.keys()), ['email'])
        self.assertEqual(content['email'], ['This field may not be blank.'])

    def test_no_password(self):
        client = Client()
        response = client.post('/users/register/', {'email': 'test_5@example.com'})
        self.assertEqual(response.status_code, 400)
        content = json.loads(response.content.decode())
        self.assertEqual(list(content.keys()), ['password'])
        self.assertEqual(content['password'], ['This field is required.'])

        response = client.post('/users/register/', {'email': 'test_5@example.com', 'password': ''})
        self.assertEqual(response.status_code, 400)
        content = json.loads(response.content.decode())
        self.assertEqual(list(content.keys()), ['password'])
        self.assertEqual(content['password'], ['This field may not be blank.'])

    def test_no_email_and_no_password(self):
        client = Client()
        response = client.post('/users/register/')
        self.assertEqual(response.status_code, 400)
        content = json.loads(response.content.decode())
        self.assertIn('email', content.keys())
        self.assertIn('password', content.keys())
        self.assertEqual(content['email'], ['This field is required.'])
        self.assertEqual(content['password'], ['This field is required.'])

    def test_existing_email(self):
        client = Client()
        response = client.post('/users/register/', {'email': 'test_6@example.com', 'password': 'password6'})
        self.assertEqual(response.status_code, 201)

        response = client.post('/users/register/', {'email': 'test_6@example.com', 'password': 'password6'})
        content = json.loads(response.content.decode())
        self.assertEqual(response.status_code, 400)
        self.assertIn('email', content.keys())
        self.assertEqual(content['email'], ['This field must be unique.'])


class TestUserProfile(TestCase):
    def test_empty_profile(self):
        client = Client()
        email = 'empty_profile@example.com'
        response = client.post('/users/register/', {'email': email, 'password': 'password1'})
        self.assertEqual(response.status_code, 201)
        content = json.loads(response.content.decode())
        token = content['api_key']
        auth_headers = {
            'HTTP_AUTHORIZATION': 'Token ' + token
        }

        response = client.get('/users/me', content_type='application/json', **auth_headers)
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content.decode())
        self.assertEqual(content['email'], email)
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

    def test_full_update(self):
        # Create User
        client = Client()
        email = 'user_profile@example.com'
        response = client.post('/users/register/', {'email': email, 'password': 'password1'})
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


class TestAuthentication(APITestCase):
    @classmethod
    def setUpClass(cls):
        cls.user = UserFactory()
        super(TestAuthentication, cls).setUpClass()

    def test_local_login_valid(self):
        data = {
            "email": self.user.email,
            "password": 'defaultpassword'
        }
        response = self.client.post('/users/login/', data=data)

        self.assertEqual(response.status_code, 200)
        self.assertIn("api_key", response.data)

    def test_local_login_invalid(self):
        data = {
            "email": self.user.email,
            "password": 'badpassword'
        }
        response = self.client.post('/users/login/', data=data)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["message"], 'Login credentials incorrect.')

    def test_local_login_disable(self):
        self.user.is_active = False
        self.user.save()
        data = {
            "email": self.user.email,
            "password": 'defaultpassword'
        }
        response = self.client.post('/users/login/', data=data)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["message"], "The account associated with this email address is suspended.")

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
        self.assertEqual(content['detail'], 'Invalid token.')

    def test_change_password(self):
        auth_headers = {'HTTP_AUTHORIZATION': "Token " + self.user.create_token()}
        response = self.client.put('/users/me/password', {'password': 'test'}, **auth_headers)
        user = CustomUser.objects.get(id=self.user.id)

        self.assertEqual(response.status_code, 200)
        user = authenticate(username=user.email, password='test')
        self.assertTrue(user.password)


class TestTwitterLogin(APITestCase):
    def stub_verify_credentials(self, data):
        httpretty.register_uri(httpretty.GET, 'https://api.twitter.com/1.1/account/verify_credentials.json',
                               body=json.dumps(data), content_type="application/json")

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

    @httpretty.activate
    def test_twitter_login_user_create(self):
        twitter_id = 'omsr4k7yta'
        self.stub_verify_credentials({'id_str': twitter_id})

        response = twitter_login("V7UoKuG529N3L92386ZdF0TE2kUGnzAp", "2ghMHZux2o02Xd47X7hsP6UH897fDmBb")
        self.assertEqual(response.status_code, 201)
        user = CustomUser.objects.get(twitter=twitter_id)
        self.assertEqual(response.data['email'], user.email)

    @httpretty.activate
    def test_twitter_login_user_exists(self):
        twitter_id = 'omsr4k7yta'
        user = UserFactory(twitter=twitter_id)
        self.stub_verify_credentials({'id_str': twitter_id})
        response = twitter_login("V7UoKuG529N3L92386ZdF0TE2kUGnzAp", "2ghMHZux2o02Xd47X7hsP6UH897fDmBb")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['email'], user.email)


class TestFacebookLogin(APITestCase):
    def stub_graph(self, data):
        httpretty.register_uri(httpretty.GET, 'https://graph.facebook.com/v2.3/me',
                               body=json.dumps(data), content_type="application/json")

    @httpretty.activate
    def test_facebook_graph_user_exists(self):
        facebook_id = 'O7bz6vG60Y'
        self.stub_graph({"email": "", "id": facebook_id})
        user = UserFactory(facebook=facebook_id)

        response = facebook_graph('Ju76xER1A5')
        user = CustomUser.objects.get(id=user.id)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(user.facebook, facebook_id)

    @httpretty.activate
    def test_facebook_graph_no_user(self):
        facebook_id = '9l0RFutSn7'
        email = "dyost@kunze.biz"
        self.stub_graph({"email": email, "id": facebook_id})
        response = facebook_graph('Ju76xER1A5')
        user = CustomUser.objects.get(facebook=facebook_id)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(user.facebook, facebook_id)
        self.assertEqual(user.email, email)

    @httpretty.activate
    def test_facebook_graph_no_user_or_email(self):
        facebook_id = 'GzQ6YzqJ7H'
        self.stub_graph({"id": facebook_id})
        response = facebook_graph('Ju76xER1A5')
        user = CustomUser.objects.get(facebook=facebook_id)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(user.facebook, facebook_id)

    @httpretty.activate
    def test_facebook_graph_link_user_with_email(self):
        user = UserFactory()
        self.stub_graph({"email": user.email, "id": 793875})
        response = facebook_graph('Ju76xER1A5')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['email'], user.email)
