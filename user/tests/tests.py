import json
from django.test import Client, TestCase
from hermes import settings
from scheme.encyption import AESCipher
from scheme.tests.factories import SchemeAccountFactory, SchemeCredentialAnswerFactory, SchemeFactory, \
    SchemeCredentialQuestionFactory
from user.tests.factories import UserFactory, UserProfileFactory, fake
from rest_framework.test import APITestCase


class TestRegisterNewUser(TestCase):
    def test_register(self):
        client = Client()
        response = client.post('/users/register/', {'email': 'test_1@example.com', 'password': 'password1'})
        content = json.loads(response.content.decode())
        self.assertEqual(response.status_code, 201)
        self.assertIn('email', content.keys())
        self.assertIn('api_key', content.keys())
        self.assertEqual(content['email'], 'test_1@example.com')
        self.assertEqual(len(content['api_key']), 36)

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
        uid = content['api_key']
        auth_headers = {
            'HTTP_AUTHORIZATION': 'Token ' + str(uid)
        }

        response = client.get('/users/{}'.format(uid), content_type='application/json', **auth_headers)
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content.decode())
        self.assertEqual(content['email'], email)
        self.assertEqual(content['uid'], uid)
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
        self.assertEqual(content['currency'], None)

    def test_full_update(self):
        # Create User
        client = Client()
        email = 'user_profile@example.com'
        response = client.post('/users/register/', {'email': email, 'password': 'password1'})
        self.assertEqual(response.status_code, 201)
        content = json.loads(response.content.decode())
        api_key = content['api_key']
        auth_headers = {
            'HTTP_AUTHORIZATION': 'Token ' + str(api_key)
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
            'currency': 'GBP'
        }
        response = client.put('/users/{}/'.format(api_key), json.dumps(data), content_type='application/json', **auth_headers)
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content.decode())
        data['uid'] = api_key
        #TODO: SORT THESE
        data['currency'] = '0'
        data['notifications'] = 0
        #TODO: Check all fields in response
        pass
        #TODO: Check all fields in model
        self.assertEqual(content, data)

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
            'HTTP_AUTHORIZATION': 'Token ' + str(uid)
        }
        client = Client()
        response = client.put('/users/{}'.format(uid), json.dumps(data), content_type='application/json', **auth_headers)
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
            'HTTP_AUTHORIZATION': 'Token ' + str(uid)
        }
        response = client.put('/users/{}/'.format(uid), json.dumps(data), content_type='application/json', **auth_headers)
        content = json.loads(response.content.decode())
        self.assertEqual(response.status_code, 200)
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
            'HTTP_AUTHORIZATION': 'Token ' + str(uid)
        }
        response = client.put('/users/{}/'.format(uid), json.dumps(data), content_type='application/json', **auth_headers)
        content = json.loads(response.content.decode())
        self.assertEqual(response.status_code, 200)
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
            'HTTP_AUTHORIZATION': 'Token ' + str(uid)
        }
        client = Client()
        response = client.put('/users/{}'.format(uid), json.dumps(data), content_type='application/json', **auth_headers)
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content.decode())
        self.assertEqual(content['uid'], str(uid))
        self.assertEqual(content['email'], new_email)

    def test_edit_unique_email(self):
        user_profile1 = UserProfileFactory()
        user_profile2 = UserProfileFactory()
        uid = user_profile1.user.uid
        data = {
            'email': user_profile2.user.email,
        }
        auth_headers = {
            'HTTP_AUTHORIZATION': 'Token ' + str(uid)
        }
        client = Client()
        response = client.put('/users/{}'.format(uid), json.dumps(data), content_type='application/json', **auth_headers)
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
            'HTTP_AUTHORIZATION': 'Token ' + str(uid)
        }
        client = Client()
        response = client.put('/users/{}'.format(uid), json.dumps(data), content_type='application/json', **auth_headers)
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content.decode())
        self.assertEqual(content['uid'], str(uid))

    def test_remove_all(self):
        user_profile = UserProfileFactory()
        uid = user_profile.user.uid
        auth_headers = {
            'HTTP_AUTHORIZATION': 'Token ' + str(uid),
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

        response = client.put('/users/{}'.format(uid), json.dumps(data),
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
        response = client.put('/users/{}/'.format(uid), json.dumps(data), content_type='application/json', **auth_headers)
        content = json.loads(response.content.decode())
        self.assertEqual(response.status_code, 200)
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


    def test_remove_partial(self):
        pass

    def test_cannot_remove_email(self):
        pass

    def test_currency_valid(self):
        pass

    def test_notifications_settings_valid(self):
        pass


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
        self.assertEqual(response.data["error"], 'Login credentials incorrect.')

    def test_local_login_disable(self):
        self.user.is_active = False
        self.user.save()
        data = {
            "email": self.user.email,
            "password": 'defaultpassword'
        }
        response = self.client.post('/users/login/', data=data)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["error"], "The account associated with this email address is suspended.")

    def test_remote_authentication_valid(self):
        client = Client()
        uid = str(self.user.uid)
        auth_headers = {
            'HTTP_AUTHORIZATION': "Token " + uid
        }
        response = client.get('/users/authenticate/', **auth_headers)
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content.decode())
        self.assertEqual(content['uid'], uid)
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


class TestSchemeAccounts(TestCase):
    def test_get_scheme_accounts(self):
        scheme = SchemeFactory()
        scheme_account = SchemeAccountFactory(scheme=scheme)
        question = SchemeCredentialQuestionFactory(scheme=scheme)
        answer = SchemeCredentialAnswerFactory(scheme_account=scheme_account)
        user = scheme_account.user
        uid = str(user.uid)
        auth_headers = {
            'HTTP_AUTHORIZATION': "Token " + str(uid),
        }
        client = Client()
        response = client.get('/users/scheme_accounts/{}/'.format(scheme_account.id), content_type='application/json', **auth_headers)
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content.decode())
        self.assertEqual(content['scheme_slug'], scheme.slug)
        self.assertEqual(content['scheme_account_id'], scheme_account.id)
        self.assertEqual(content['user_id'], scheme_account.user.id)
        decrypted_credentials = AESCipher(settings.AES_KEY.encode()).decrypt(content['credentials'])
        credentials = json.loads(decrypted_credentials)
        # self.assertEqual(credentials['username'], scheme_account.username)
        # self.assertEqual(credentials['card_number'], scheme_account.card_number)
        # self.assertEqual(credentials['membership_number'], str(scheme_account.membership_number))
        # self.assertEqual(credentials['password'], scheme_account.decrypt())
        # self.assertEqual(credentials['extra'], {question.type: answer.decrypt()})

