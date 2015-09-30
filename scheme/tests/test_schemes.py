import json
from rest_framework.test import APITestCase
from rest_framework.utils.serializer_helpers import ReturnDict, ReturnList
from scheme.tests import factories
from scheme.tests.factories import SchemeCredentialQuestionFactory


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
        SchemeCredentialQuestionFactory()
        response = self.client.get('/schemes/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(type(response.data), ReturnList)
        content = json.loads(response.content.decode())
        self.assertTrue(response.data)
        self.assertEqual(len(content[1]['questions']), 1)

    def test_scheme_list_includes_questions(self):
        self.assertTrue(False)

    def test_scheme_item(self):
        response = self.client.get('/schemes/{0}'.format(self.scheme.id))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(type(response.data), ReturnDict)
        self.assertEqual(response.data['id'], self.scheme.id)

