import json
from rest_framework.test import APITestCase
from rest_framework.utils.serializer_helpers import ReturnDict, ReturnList
from scheme.tests import factories
from scheme.encyption import AESCipher
from django.conf import settings
from scheme.models import SchemeAccount
from scheme.tests.factories import SchemeCredentialQuestionFactory, SchemeCredentialAnswerFactory, SchemeFactory
from user.tests.factories import UserFactory


class TestScheme(APITestCase):
    @classmethod
    def setUpClass(cls):
        cls.scheme_account_answer = factories.SchemeCredentialAnswerFactory()
        cls.scheme_account = cls.scheme_account_answer.scheme_account
        cls.user = cls.scheme_account.user
        cls.auth_headers = {
            'HTTP_AUTHORIZATION': 'Token ' + str(cls.user.uid),
        }
        cls.scheme = cls.scheme_account.scheme
        super(TestScheme, cls).setUpClass()

    def test_scheme_list(self):
        question = SchemeCredentialQuestionFactory()
        response = self.client.get('/schemes/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(type(response.data), ReturnList)
        content = json.loads(response.content.decode())
        self.assertTrue(response.data)
        self.assertEqual(len(content[1]['questions']), 1)

    def test_scheme_list_includes_questions(self):
        pass

    def test_scheme_item(self):
        response = self.client.get('/schemes/{0}'.format(self.scheme.id))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(type(response.data), ReturnDict)
        self.assertEqual(response.data['id'], self.scheme.id)

    #TODO:REPURPOSE
    def test_get_scheme_accounts(self):
        response = self.client.get('/schemes/accounts/{0}'.format(self.scheme_account.id), **self.auth_headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(type(response.data), ReturnDict)
        self.assertEqual(response.data['id'], self.scheme_account.id)



    def test_patch_schemes_accounts(self):
        data = {'card_number': 'new-card-number'}
        response = self.client.patch('/schemes/accounts/{0}'.format(self.scheme_account.id), data=data, **self.auth_headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(type(response.data), ReturnDict)
#        self.assertEqual(response.data['card_number'], 'new-card-number')

    def test_delete_schemes_accounts(self):
        response = self.client.delete('/schemes/accounts/{0}'.format(self.scheme_account.id), **self.auth_headers)
        deleted_scheme_account = SchemeAccount.objects.get(id=self.scheme_account.id)

        self.assertEqual(response.status_code, 204)
        self.assertEqual(deleted_scheme_account.status, SchemeAccount.DELETED)

        response = self.client.get('/schemes/accounts/{0}'.format(self.scheme_account.id), **self.auth_headers)
        self.assertEqual(response.status_code, 404)

    def test_post_schemes_account_answer(self):
        data = {
            "scheme_account": self.scheme_account.id,
            "type": self.scheme_account_answer.type,
            "answer": "London"
        }
        response = self.client.post('/schemes/accounts/credentials/', data=data, **self.auth_headers)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["answer"], data["answer"])
        self.assertIn("id", response.data)


class TestSchemeAccount(APITestCase):
    @classmethod
    def setUpClass(cls):
        cls.user = UserFactory()
        cls.auth_headers = {
            'HTTP_AUTHORIZATION': 'Token ' + str(cls.user.uid),
        }
        super(TestSchemeAccount, cls).setUpClass()

    def test_post_schemes_accounts(self):
        scheme = SchemeFactory()
        data = {
                'scheme': scheme.id,
                'user': self.user.id
                }
        response = self.client.post('/schemes/accounts/', data=data, **self.auth_headers)
        self.assertEqual(response.status_code, 201)

    def test_post_scheme_account_with_answers(self):
        scheme = SchemeFactory()
        username_question = SchemeCredentialQuestionFactory(scheme=scheme, type='username')
        card_no_question = SchemeCredentialQuestionFactory(scheme=scheme, type='card_no')
        password_question = SchemeCredentialQuestionFactory(scheme=scheme, type='password')
        data = {
                'scheme': scheme.id,
                'user': self.user.id,
                username_question.type: 'andrew',
                card_no_question.type: '1234',
                password_question.type: 'password'
        }
        response = self.client.post('/schemes/accounts/', data=data, **self.auth_headers)
        content = json.loads(response.data)
        self.assertEqual(content['scheme_id'], scheme.id)
        self.assertEqual(content['order'], 0)
        self.assertEqual(content['username'], 'andrew')
        self.assertEqual(content['password'], 'password')
        self.assertEqual(content['card_no'], '1234')

    def test_update_scheme_account_with_answers(self):
        scheme = SchemeFactory()
        username_question = SchemeCredentialQuestionFactory(scheme=scheme, type='username')
        card_no_question = SchemeCredentialQuestionFactory(scheme=scheme, type='card_no')
        password_question = SchemeCredentialQuestionFactory(scheme=scheme, type='password')
        data = {
                'scheme': scheme.id,
                'user': self.user.id,
                username_question.type: 'andrew',
                card_no_question.type: '1234',
                password_question.type: 'password'
        }
        response = self.client.post('/schemes/accounts/', data=data, **self.auth_headers) #content_type='application/json'
        self.assertEqual(response.status_code, 201)
        content = json.loads(response.data)
        self.assertEqual(content['scheme_id'], scheme.id)
        self.assertEqual(content['order'], 0)
        self.assertEqual(content['username'], 'andrew')
        self.assertEqual(content['password'], 'password')
        self.assertEqual(content['card_no'], '1234')
        data = {
                'scheme': scheme.id,
                'user': self.user.id,
                username_question.type: 'andrew',
                card_no_question.type: '1234',
                password_question.type: 'password2'
        }
        response = self.client.post('/schemes/accounts/', data=data, **self.auth_headers)
        self.assertEqual(response.status_code, 400)
        response = self.client.put('/schemes/accounts/{}'.format(scheme.id), data=data, **self.auth_headers)
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.data)
        self.assertEqual(content['scheme_id'], scheme.id)
        self.assertEqual(content['order'], 0)
        self.assertEqual(content['username'], 'andrew')
        self.assertEqual(content['password'], 'password2')
        self.assertEqual(content['card_no'], '1234')




