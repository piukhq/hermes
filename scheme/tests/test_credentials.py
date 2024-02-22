import json
from typing import NamedTuple

from django.conf import settings
from django.core.exceptions import ValidationError
from rest_framework.exceptions import ErrorDetail

from history.utils import GlobalMockAPITestCase
from scheme.credentials import BARCODE, CARD_NUMBER, LAST_NAME, MERCHANT_IDENTIFIER, PASSWORD
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


class OptionalJourneyFieldsTestData(NamedTuple):
    test_case: str
    data: dict[str, bool]


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
            options=SchemeCredentialQuestion.LINK,
            auth_field=True,
        )
        cls.merchant_id_question = SchemeCredentialQuestionFactory(
            scheme=cls.scheme,
            type=MERCHANT_IDENTIFIER,
            label=MERCHANT_IDENTIFIER,
            third_party_identifier=True,
            options=SchemeCredentialQuestion.MERCHANT_IDENTIFIER,
        )
        GenerateJWToken(client.organisation.name, client.secret, cls.bundle.bundle_id, external_id).get_token()
        cls.auth_headers = {
            "HTTP_AUTHORIZATION": f"Token {settings.SERVICE_API_KEY}",
            "HTTP_BINK_USER_ID": cls.user.id,
        }

    def test_clean_answer(self):
        question = SchemeCredentialQuestionFactory(type=PASSWORD)
        answer = SchemeCredentialAnswerFactory(answer="sdfsdfsdf", question=question)
        self.assertEqual(answer.clean_answer(), "****")

    def test_internal_update_main_answer_to_existing_credential_fails(self):
        # The credential lookup to check for existing accounts is done on the scheme account
        # fields "card_number", "barcode", "alt_main_answer", or "merchant_identifier",
        # not on the SchemeCredentialAnswer records.
        for field in [CARD_NUMBER, BARCODE, MERCHANT_IDENTIFIER]:
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
                elif field == MERCHANT_IDENTIFIER:
                    SchemeCredentialAnswerFactory(
                        question=self.merchant_id_question,
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
                elif field == MERCHANT_IDENTIFIER:
                    ans = SchemeAccountCredentialAnswer.objects.get(
                        question=self.merchant_id_question,
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
        for field in [CARD_NUMBER, BARCODE, MERCHANT_IDENTIFIER]:
            with self.subTest(field=field):
                answer = "1111"
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

    def test_clean_credential_questions_optional_failures(self):
        journey_fields_data: list[OptionalJourneyFieldsTestData] = [
            OptionalJourneyFieldsTestData(
                test_case="Both Add & Auth fields are selected to be optional",
                data={
                    "add_field": True,
                    "auth_field": True,
                    "register_field": False,
                    "enrol_field": False,
                },
            ),
            OptionalJourneyFieldsTestData(
                test_case="Both Add & Auth and also register field are selected to be optional",
                data={
                    "add_field": True,
                    "auth_field": True,
                    "register_field": True,
                    "enrol_field": False,
                },
            ),
            OptionalJourneyFieldsTestData(
                test_case="All journey fields are selected to be optional",
                data={
                    "add_field": True,
                    "auth_field": True,
                    "register_field": True,
                    "enrol_field": True,
                },
            ),
            OptionalJourneyFieldsTestData(
                test_case="Add field and also Enrol and Register fields are selected to be optional",
                data={
                    "add_field": True,
                    "auth_field": False,
                    "register_field": True,
                    "enrol_field": True,
                },
            ),
            OptionalJourneyFieldsTestData(
                test_case="Auth field and also Enrol and Register fields are selected to be optional",
                data={
                    "add_field": False,
                    "auth_field": True,
                    "register_field": True,
                    "enrol_field": True,
                },
            ),
            OptionalJourneyFieldsTestData(
                test_case="None of the journey fields are selected to be optional",
                data={
                    "add_field": False,
                    "auth_field": False,
                    "register_field": False,
                    "enrol_field": False,
                },
            ),
        ]

        for journey_fields in journey_fields_data:
            question = SchemeCredentialQuestionFactory(
                type=CARD_NUMBER,
                label=CARD_NUMBER,
                manual_question=True,
                add_field=journey_fields.data["add_field"],
                auth_field=journey_fields.data["auth_field"],
                register_field=journey_fields.data["enrol_field"],
                enrol_field=journey_fields.data["enrol_field"],
                is_optional=True,
            )
            with self.assertRaises(ValidationError) as e:
                question.clean()

            self.assertEqual(len(e.exception.message_dict.keys()), 1)
            self.assertEqual(next(iter(e.exception.message_dict.keys())), "is_optional")
            self.assertEqual(
                e.exception.message_dict["is_optional"],
                ["This field can only be used for enrol & register credentials."],
            )

    def test_clean_credential_questions_optional_success(self):
        journey_fields_data: list[OptionalJourneyFieldsTestData] = [
            OptionalJourneyFieldsTestData(
                test_case="Both Enrol & Register are selected to be optional",
                data={
                    "add_field": False,
                    "auth_field": False,
                    "register_field": True,
                    "enrol_field": True,
                },
            ),
            OptionalJourneyFieldsTestData(
                test_case="Only register field is selected to be optional",
                data={
                    "add_field": False,
                    "auth_field": False,
                    "register_field": True,
                    "enrol_field": False,
                },
            ),
            OptionalJourneyFieldsTestData(
                test_case="Only enrol field is selected to be optional",
                data={
                    "add_field": False,
                    "auth_field": False,
                    "register_field": False,
                    "enrol_field": True,
                },
            ),
        ]

        for journey_fields in journey_fields_data:
            question = SchemeCredentialQuestionFactory(
                type=CARD_NUMBER,
                label=CARD_NUMBER,
                manual_question=True,
                add_field=journey_fields.data["add_field"],
                auth_field=journey_fields.data["auth_field"],
                register_field=journey_fields.data["enrol_field"],
                enrol_field=journey_fields.data["enrol_field"],
                is_optional=True,
            )
        question.clean()
