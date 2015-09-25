from rest_framework.test import APITestCase
from rest_framework.utils.serializer_helpers import ReturnDict, ReturnList
from scheme.tests import factories
from scheme.encyption import AESCipher
from django.conf import settings
from scheme.models import SchemeAccount


class TestScheme(APITestCase):
    @classmethod
    def setUpClass(cls):
        cls.scheme_account_answer = factories.SchemeCredentialAnswerFactory()
        cls.scheme_account = cls.scheme_account_answer.scheme_account
        cls.user = cls.scheme_account.user
        cls.auth_headers = {
            'HTTP_AUTHORIZATION': str(cls.user.uid),
        }
        cls.scheme = cls.scheme_account.scheme
        super(TestScheme, cls).setUpClass()

    def test_scheme_list(self):
        response = self.client.get('/schemes/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(type(response.data), ReturnList)
        self.assertTrue(response.data)

    def test_scheme_item(self):
        response = self.client.get('/schemes/{0}'.format(self.scheme.id))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(type(response.data), ReturnDict)
        self.assertEqual(response.data['id'], self.scheme.id)

    def test_get_schemes_accounts(self):
        response = self.client.get('/schemes/accounts/{0}'.format(self.scheme_account.id), **self.auth_headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(type(response.data), ReturnDict)
        self.assertEqual(response.data['id'], self.scheme_account.id)

    def test_post_schemes_accounts(self):
        data = {'username': 'herman.ida',
                'scheme': self.scheme.id,
                'password': 'test',
                'user': self.user.id,
                'membership_number': '4786',
                'card_number': '6011687956185350'}
        response = self.client.post('/schemes/accounts/', data=data, **self.auth_headers)
        self.assertEqual(response.status_code, 201)
        decoded_password = AESCipher(settings.AES_KEY.encode()).decrypt(response.data['password'])

        self.assertNotEqual(data["password"], response.data['password'])
        self.assertEqual(data["password"], decoded_password)
        self.assertIn('created', response.data)

    def test_patch_schemes_accounts(self):
        data = {'card_number': 'new-card-number'}
        response = self.client.patch('/schemes/accounts/{0}'.format(self.scheme_account.id), data=data, **self.auth_headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(type(response.data), ReturnDict)
        self.assertEqual(response.data['card_number'], 'new-card-number')

    def test_delete_schemes_accounts(self):
        response = self.client.delete('/schemes/accounts/{0}'.format(self.scheme_account.id), **self.auth_headers)
        deleted_scheme_account = SchemeAccount.objects.get(id=self.scheme_account.id)

        self.assertEqual(response.status_code, 204)
        self.assertEqual(deleted_scheme_account.status, SchemeAccount.DELETED)

        response = self.client.get('/schemes/accounts/{0}'.format(self.scheme_account.id), **self.auth_headers)
        self.assertEqual(response.status_code, 404)

    def test_post_schemes_account_question(self):
        data = {
            "scheme_account": self.scheme_account.id,
            "question": self.scheme_account_answer.question.id,
            "answer": "London"
        }
        response = self.client.post('/schemes/accounts/questions/', data=data, **self.auth_headers)
        self.assertEqual(response.status_code, 201)
        self.assertNotEqual(response.data["answer"], data["answer"])
        self.assertIn("id", response.data)

    def test_get_schemes_account_question(self):
        response = self.client.get('/schemes/accounts/questions/{0}'.format(self.scheme_account_answer.id), **self.auth_headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(type(response.data), ReturnDict)
        self.assertIn("id", response.data)
