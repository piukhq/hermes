import json
from django.test import Client, TestCase


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




