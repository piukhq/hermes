import json
from rest_framework.test import APITestCase
from rest_framework.utils.serializer_helpers import ReturnDict, ReturnList
from scheme.tests import factories
from scheme.tests.factories import SchemeCredentialQuestionFactory, SchemeImageFactory, SchemeFactory


class TestScheme(APITestCase):
    @classmethod
    def setUpClass(cls):
        cls.scheme_account_answer = factories.SchemeCredentialAnswerFactory()
        cls.scheme_account = cls.scheme_account_answer.scheme_account
        cls.user = cls.scheme_account.user
        cls.auth_headers = {'HTTP_AUTHORIZATION': 'Token ' + cls.user.create_token()}
        cls.scheme = cls.scheme_account.scheme
        question = SchemeCredentialQuestionFactory(scheme=cls.scheme)
        cls.scheme.primary_question = question
        cls.scheme.save()
        super(TestScheme, cls).setUpClass()

    def test_scheme_list(self):
        scheme = SchemeFactory()
        question = SchemeCredentialQuestionFactory(scheme=scheme)
        scheme.primary_question = question
        scheme.save()
        SchemeImageFactory(scheme=scheme)
        response = self.client.get('/schemes/', **self.auth_headers)
        self.assertEqual(response.status_code, 200,)
        self.assertEqual(type(response.data), ReturnList)
        content = json.loads(response.content.decode())
        self.assertTrue(response.data)
        for resp_scheme in content:
            self.assertIn('has_points', resp_scheme.keys())
            self.assertIn('has_transactions', resp_scheme.keys())
            if resp_scheme['id'] == scheme.id:
                # Question related assertions
                self.assertEqual(len(resp_scheme['questions']), 1)
                # Image related assertions
                self.assertEqual(len(resp_scheme['images']), 1)

    def test_scheme_item(self):
        response = self.client.get('/schemes/{0}'.format(self.scheme.id), **self.auth_headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(type(response.data), ReturnDict)
        self.assertEqual(response.data['id'], self.scheme.id)
