from history.utils import GlobalMockAPITestCase
from scheme.models import SchemeCredentialQuestion
from scheme.tests.factories import (
    SchemeAccountFactory,
    SchemeCredentialAnswerFactory,
    SchemeCredentialQuestionFactory,
    SchemeFactory,
)
from ubiquity.tests.factories import SchemeAccountEntryFactory


class TestInvalidRegex(GlobalMockAPITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.scheme1 = SchemeFactory()
        cls.question = SchemeCredentialQuestionFactory(
            scheme=cls.scheme1, type="barcode", options=SchemeCredentialQuestion.LINK
        )
        cls.scheme_account_1 = SchemeAccountFactory(scheme=cls.scheme1)
        cls.scheme_account_entry = SchemeAccountEntryFactory(scheme_account=cls.scheme_account_1)
        SchemeCredentialAnswerFactory(scheme_account=cls.scheme_account_1, question=cls.question, answer="1234",
                                      scheme_account_entry=cls.scheme_account_entry)
        cls.user = cls.scheme_account_entry.user

        cls.scheme2 = SchemeFactory()
        SchemeCredentialQuestionFactory(scheme=cls.scheme2, type="barcode", options=SchemeCredentialQuestion.LINK)
        cls.scheme_account_2 = SchemeAccountFactory(scheme=cls.scheme2)
        cls.scheme_account_entry_2 = SchemeAccountEntryFactory(scheme_account=cls.scheme_account_2, user=cls.user)
        SchemeCredentialAnswerFactory(scheme_account=cls.scheme_account_2, question=cls.question, answer="1234",
                                      scheme_account_entry=cls.scheme_account_entry_2)

        cls.auth_headers = {"HTTP_AUTHORIZATION": "Token " + cls.user.create_token()}

    def test_incorrect_regex(self):
        self.scheme1.card_number_regex = "^-?[0-9]+$"
        self.scheme1.barcode_regex = "^-?[0-9]+$"
        self.scheme1.save()
        response = self.client.get("/schemes/accounts/", **self.auth_headers)
        self.assertEqual(response.status_code, 200)

    def test_invalid_regex(self):
        self.scheme1.card_number_regex = "^-?[0-9+$"
        self.scheme1.barcode_regex = "^-?[0-9+$"
        self.scheme1.save()
        response = self.client.get("/schemes/accounts/", **self.auth_headers)
        self.assertEqual(response.status_code, 200)
