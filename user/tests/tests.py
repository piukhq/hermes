import json
from django.test import Client, TestCase
from user.tests.factories import UserFactory, UserProfileFactory, fake


class TestRegisterNewUser(TestCase):

    def test_register(self):
        client = Client()
        response = client.post('/users/register/', {'email': 'test_1@example.com', 'password': 'password1'})
        content = json.loads(response.content.decode())
        self.assertEqual(response.status_code, 201)
        self.assertIn('email', content.keys())
        self.assertIn('uid', content.keys())
        self.assertEqual(content['email'], 'test_1@example.com')
        self.assertEqual(len(content['uid']), 36)

    def test_uid_is_unique(self):
        client = Client()
        response = client.post('/users/register/', {'email': 'test_2@example.com', 'password': 'password2'})
        self.assertEqual(response.status_code, 201)
        content = json.loads(response.content.decode())
        uid_1 = content['uid']

        response = client.post('/users/register/', {'email': 'test_3@example.com', 'password': 'password3'})
        self.assertEqual(response.status_code, 201)
        content = json.loads(response.content.decode())
        uid_2 = content['uid']

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
        uid = content['uid']

        response = client.get('/users/{}/'.format(uid), content_type='application/json')
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
        uid = content['uid']
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
        response = client.put('/users/{}/'.format(uid), json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content.decode())
        data['uid'] = uid
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
        client = Client()
        response = client.put('/users/{}/'.format(uid), json.dumps(data), content_type='application/json')
        content = json.loads(response.content.decode())
        self.assertEqual(response.status_code, 200)
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
        response = client.put('/users/{}/'.format(uid), json.dumps(data), content_type='application/json')
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
        response = client.put('/users/{}/'.format(uid), json.dumps(data), content_type='application/json')
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
        client = Client()
        response = client.put('/users/{}/'.format(uid), json.dumps(data), content_type='application/json')
        content = json.loads(response.content.decode())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(content['uid'], str(uid))
        self.assertEqual(content['email'], new_email)

    def test_edit_unique_email(self):
        user_profile1 = UserProfileFactory()
        user_profile2 = UserProfileFactory()
        uid = user_profile1.user.uid
        data = {
            'email': user_profile2.user.email,
        }
        client = Client()
        response = client.put('/users/{}/'.format(uid), json.dumps(data), content_type='application/json')
        content = json.loads(response.content.decode())
        self.assertEqual(response.status_code, 400)
        self.assertEqual(content['email'], ['This field must be unique.'])

    def test_cannot_edit_uid(self):
        pass

    def test_remove_all(self):
        pass

    def test_remove_partial(self):
        pass

    def test_currency_valid(self):
        pass

    def test_notifications_settings_valid(self):
        pass






