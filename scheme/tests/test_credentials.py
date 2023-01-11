import json

from django.conf import settings
from rest_framework.exceptions import ErrorDetail

from history.utils import GlobalMockAPITestCase
from scheme.credentials import BARCODE, CARD_NUMBER, LAST_NAME, PASSWORD
from scheme.models import SchemeAccountCredentialAnswer, SchemeBundleAssociation, SchemeCredentialQuestion
from scheme.tests.factories import (
    SchemeAccountFactory,
    SchemeBalanceDetailsFactory,
    SchemeBundleAssociationFactory,
    SchemeCredentialAnswerFactory,
    SchemeCredentialQuestionFactory,
    SchemeFactory,
)
from ubiquity.models import AccountLinkStatus
from ubiquity.tests.factories import SchemeAccountEntryFactory
from ubiquity.tests.property_token import GenerateJWToken
from user.tests.factories import (
    ClientApplicationBundleFactory,
    ClientApplicationFactory,
    OrganisationFactory,
    UserFactory,
)


class TestCredentials(GlobalMockAPITestCase):
    @classmethod
    def setUpTestData(cls):
        organisation = OrganisationFactory(name="set up authentication for credentials")
        client = ClientApplicationFactory(organisation=organisation, name="set up credentials application")
        cls.bundle = ClientApplicationBundleFactory(bundle_id="test.credentials.fake", client=client)
        external_id = "credentials@user.com"
        cls.user = UserFactory(external_id=external_id, client=client, email=external_id)
        cls.scheme = SchemeFactory()
        cls.scheme_bundle_association = SchemeBundleAssociationFactory(
            scheme=cls.scheme, bundle=cls.bundle, status=SchemeBundleAssociation.ACTIVE
        )
        SchemeBalanceDetailsFactory(scheme_id=cls.scheme)
        SchemeCredentialQuestionFactory(
            scheme=cls.scheme, type=CARD_NUMBER, label=CARD_NUMBER, manual_question=True, add_field=True
        )
        SchemeCredentialQuestionFactory(
            scheme=cls.scheme, type=BARCODE, label=BARCODE, scan_question=True, add_field=True
        )

        SchemeCredentialQuestionFactory(scheme=cls.scheme, type=PASSWORD, label=PASSWORD, auth_field=True)
        SchemeCredentialQuestionFactory(
            scheme=cls.scheme,
            type=LAST_NAME,
            label=LAST_NAME,
            third_party_identifier=True,
            options=SchemeCredentialQuestion.LINK,
            auth_field=True,
        )
        GenerateJWToken(client.organisation.name, client.secret, cls.bundle.bundle_id, external_id).get_token()
        cls.auth_headers = {
            "HTTP_AUTHORIZATION": "Token {}".format(settings.SERVICE_API_KEY),
            "HTTP_BINK_USER_ID": cls.user.id,
        }

    def test_clean_answer(self):
        question = SchemeCredentialQuestionFactory(type=PASSWORD)
        answer = SchemeCredentialAnswerFactory(answer="sdfsdfsdf", question=question)
        self.assertEqual(answer.clean_answer(), "****")

    def test_internal_update_main_answer_to_existing_credential_fails(self):
        # The credential lookup to check for existing accounts is done on the scheme account
        # fields "card_number", "barcode", and/or "alt_main_answer", not on the SchemeCredentialAnswer records.
        for field in [CARD_NUMBER, BARCODE]:
            with self.subTest(field=field):
                answer = "1111"
                SchemeAccountFactory(scheme=self.scheme, **{field: answer})

                scheme_account2 = SchemeAccountFactory(scheme=self.scheme)
                scheme_account_entry_2 = SchemeAccountEntryFactory(scheme_account=scheme_account2, user=self.user)

                if field == BARCODE:
                    SchemeCredentialAnswerFactory(
                        question=self.scheme.scan_question,
                        answer="2222",
                        scheme_account_entry=scheme_account_entry_2,
                    )
                else:
                    SchemeCredentialAnswerFactory(
                        question=self.scheme.manual_question,
                        answer="2222",
                        scheme_account_entry=scheme_account_entry_2,
                    )

                payload = {field: answer}

                resp = self.client.put(
                    f"/schemes/accounts/{scheme_account2.id}/credentials",
                    data=json.dumps(payload),
                    content_type="application/json",
                    **self.auth_headers,
                )

                self.assertEqual(400, resp.status_code)
                self.assertEqual(
                    {
                        "non_field_errors": [
                            ErrorDetail(string="An account already exists with the given credentials", code="invalid")
                        ]
                    },
                    resp.data,
                )

                if field == BARCODE:
                    ans = SchemeAccountCredentialAnswer.objects.get(
                        question=self.scheme.scan_question,
                        scheme_account_entry=scheme_account_entry_2,
                    )
                else:
                    ans = SchemeAccountCredentialAnswer.objects.get(
                        question=self.scheme.manual_question,
                        scheme_account_entry=scheme_account_entry_2,
                    )

                self.assertNotEqual(ans, answer)
                scheme_account_entry_2.refresh_from_db()
                self.assertEqual(AccountLinkStatus.ACCOUNT_ALREADY_EXISTS, scheme_account_entry_2.link_status)

    def test_internal_update_existing_main_answer_with_same_credential_is_accepted(self):
        for field in [CARD_NUMBER, BARCODE]:
            with self.subTest(field=field):
                answer = "1111"
                if field == "card_number":
                    # If card number field leave blank - metis put will always override existing setting
                    # required for SquareMeal trusted channels where card number not given
                    scheme_account = SchemeAccountFactory(scheme=self.scheme)
                    self.assertEqual(scheme_account.card_number, "")
                else:
                    scheme_account = SchemeAccountFactory(scheme=self.scheme, **{field: answer})

                SchemeAccountEntryFactory(scheme_account=scheme_account, user=self.user)

                payload = {field: answer}

                resp = self.client.put(
                    f"/schemes/accounts/{scheme_account.id}/credentials",
                    data=json.dumps(payload),
                    content_type="application/json",
                    **self.auth_headers,
                )
                self.assertEqual(200, resp.status_code)
                self.assertEqual({"updated": [field]}, resp.data)
                if field == "card_number":
                    scheme_account.refresh_from_db()
                    self.assertEqual(scheme_account.card_number, answer)
