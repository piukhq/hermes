from django.test import TestCase
from scheme.models import SchemeCredentialQuestion
from scheme.tests.factories import SchemeAccountFactory, SchemeFactory, SchemeCredentialQuestionFactory, \
    SchemeCredentialAnswerFactory


class TestInvalidRegex(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scheme1 = SchemeFactory()
        cls.question = SchemeCredentialQuestionFactory(scheme=cls.scheme1,
                                                       type='barcode',
                                                       options=SchemeCredentialQuestion.LINK)
        cls.scheme_account_1 = SchemeAccountFactory(scheme=cls.scheme1)
        SchemeCredentialAnswerFactory(scheme_account=cls.scheme_account_1, question=cls.question, answer='1234')
        cls.user = cls.scheme_account_1.user

        cls.scheme2 = SchemeFactory()
        SchemeCredentialQuestionFactory(scheme=cls.scheme2, type='barcode', options=SchemeCredentialQuestion.LINK)
        cls.scheme_account_2 = SchemeAccountFactory(scheme=cls.scheme2, user=cls.user)
        SchemeCredentialAnswerFactory(scheme_account=cls.scheme_account_2, question=cls.question, answer='1234')

        cls.auth_headers = {'HTTP_AUTHORIZATION': 'Token ' + cls.user.create_token()}
        super().setUpClass()

    def test_incorrect_regex(self):
        self.scheme1.card_number_regex = "^-?[0-9]+$"
        self.scheme1.barcode_regex = "^-?[0-9]+$"
        self.scheme1.save()
        response = self.client.get('/schemes/accounts/', **self.auth_headers)
        self.assertEqual(response.status_code, 200)

    def test_invalid_regex(self):
        self.scheme1.card_number_regex = "^-?[0-9+$"
        self.scheme1.barcode_regex = "^-?[0-9+$"
        self.scheme1.save()
        response = self.client.get('/schemes/accounts/', **self.auth_headers)
        self.assertEqual(response.status_code, 200)
