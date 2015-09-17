from rest_framework.test import APITestCase
from rest_framework.utils.serializer_helpers import ReturnDict, ReturnList
from scheme.tests import factories



class TestScheme(APITestCase):
    @classmethod
    def setUpClass(cls):
        cls.scheme_account_question = factories.SchemeAccountSecurityQuestionFactory()
        cls.scheme_account = cls.scheme_account_question.scheme_account
        cls.user = cls.scheme_account.user
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
        response = self.client.get('/schemes/accounts/{0}'.format(self.scheme_account.id))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(type(response.data), ReturnDict)
        self.assertEqual(response.data['id'], self.scheme_account.id)
