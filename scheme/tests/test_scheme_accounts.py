import json
from rest_framework.test import APITestCase
from scheme.tests.factories import SchemeFactory, SchemeCredentialQuestionFactory, SchemeCredentialAnswerFactory
from user.tests.factories import UserFactory
from scheme.models import SchemeAccount
from rest_framework.utils.serializer_helpers import ReturnDict, ReturnList
from scheme.credentials import PASSWORD, CARD_NUMBER, USER_NAME


class TestSchemeAccount(APITestCase):
    @classmethod
    def setUpClass(cls):
        cls.scheme_account_answer = SchemeCredentialAnswerFactory(type=USER_NAME)
        cls.scheme_account = cls.scheme_account_answer.scheme_account
        cls.scheme = cls.scheme_account.scheme
        cls.user = cls.scheme_account.user
        cls.scheme.primary_question = SchemeCredentialQuestionFactory(scheme=cls.scheme, type=USER_NAME)
        cls.scheme.save()

        cls.auth_headers = {
            'HTTP_AUTHORIZATION': 'Token ' + str(cls.user.uid),
        }
        super(TestSchemeAccount, cls).setUpClass()

    def test_post_schemes_accounts(self):
        scheme = SchemeFactory()
        data = {
                'scheme': scheme.id,
                }
        response = self.client.post('/schemes/accounts/', data=data, **self.auth_headers)
        self.assertEqual(response.status_code, 201)

    def test_post_scheme_account_with_answers(self):
        scheme = SchemeFactory()
        username_question = SchemeCredentialQuestionFactory(scheme=scheme, type=USER_NAME)
        card_no_question = SchemeCredentialQuestionFactory(scheme=scheme, type=CARD_NUMBER)
        password_question = SchemeCredentialQuestionFactory(scheme=scheme, type=PASSWORD)
        data = {
                'scheme': scheme.id,
                username_question.type: 'andrew',
                card_no_question.type: '1234',
                password_question.type: 'password'
        }
        response = self.client.post('/schemes/accounts/', data=data, **self.auth_headers)
        self.assertEqual(response.status_code, 201)
        content = response.data
        self.assertEqual(content['scheme_id'], scheme.id)
        self.assertEqual(content['order'], 0)
        self.assertEqual(content['user_name'], 'andrew')
        self.assertEqual(content['password'], 'password')
        self.assertEqual(content['card_number'], '1234')

    def test_post_scheme_account_midas_call_with_points(self):
        scheme = SchemeFactory(name="Boots", slug="advantage-card")
        username_question = SchemeCredentialQuestionFactory(scheme=scheme, type='user_name')
        password_question = SchemeCredentialQuestionFactory(scheme=scheme, type='password')
        data = {
                'scheme': scheme.id,
                username_question.type: 'julie.gormley100@gmail.com',
                password_question.type: 'RAHansbrics5'
        }
        response = self.client.post('/schemes/accounts/', data=data, **self.auth_headers)
        self.assertEqual(response.status_code, 201)
        content = json.loads(response.data)
        self.assertEqual(content['scheme_id'], scheme.id)


    def test_update_scheme_account_with_answers(self):
        scheme = SchemeFactory()

        username_question = SchemeCredentialQuestionFactory(scheme=scheme, type=USER_NAME)
        card_no_question = SchemeCredentialQuestionFactory(scheme=scheme, type=CARD_NUMBER)
        password_question = SchemeCredentialQuestionFactory(scheme=scheme, type=PASSWORD)
        scheme.primary_question = username_question
        scheme.save()
        data = {
                'scheme': scheme.id,
                username_question.type: 'andrew',
                card_no_question.type: '1234',
                password_question.type: 'password'
        }
        response = self.client.post('/schemes/accounts/', data=data, **self.auth_headers) #content_type='application/json'
        self.assertEqual(response.status_code, 201)
        content = json.loads(response.data)
        self.assertEqual(content['scheme_id'], scheme.id)
        self.assertEqual(content['order'], 0)
        self.assertEqual(content['user_name'], 'andrew')
        self.assertEqual(content['password'], 'password')
        self.assertEqual(content['card_number'], '1234')
        data = {
                'scheme': scheme.id,
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
        self.assertEqual(content['user_name'], 'andrew')
        self.assertEqual(content['password'], 'password2')
        self.assertEqual(content['card_number'], '1234')

    #TODO:REPURPOSE
    def test_get_scheme_accounts(self):
        response = self.client.get('/schemes/accounts/{0}'.format(self.scheme_account.id), **self.auth_headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(type(response.data), ReturnDict)
        self.assertEqual(response.data['id'], self.scheme_account.id)

    def test_patch_schemes_accounts(self):
        data = {'order': 5,
                'scheme': 200}
        response = self.client.patch('/schemes/accounts/{0}'.format(self.scheme_account.id), data=data,
                                     **self.auth_headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['scheme'], self.scheme_account.scheme.id)  # this shouldn't change
        self.assertEqual(response.data['order'], 5)

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

    def test_list_schemes_accounts(self):
        response = self.client.get('/schemes/accounts', **self.auth_headers)
        self.assertEqual(type(response.data), ReturnList)
        self.assertEqual(response.data[0]['scheme']['name'], self.scheme.name)
        self.assertEqual(response.data[0]['primary_answer'], self.scheme_account_answer.answer)

