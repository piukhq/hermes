import json
import secrets
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from requests.exceptions import ConnectionError as RequestConnectionError
from rest_framework.utils.serializer_helpers import ReturnDict

from history.utils import GlobalMockAPITestCase
from scheme.credentials import (
    ADDRESS_1,
    ADDRESS_2,
    BARCODE,
    CARD_NUMBER,
    CREDENTIAL_TYPES,
    EMAIL,
    FIRST_NAME,
    LAST_NAME,
    PASSWORD,
    PHONE,
    TITLE,
    TOWN_CITY,
    USER_NAME,
)
from scheme.encryption import AESCipher
from scheme.models import (
    ConsentStatus,
    JourneyTypes,
    Scheme,
    SchemeAccount,
    SchemeBundleAssociation,
    SchemeCredentialQuestion,
    UserConsent,
)
from scheme.serializers import LinkSchemeSerializer
from scheme.tests.factories import (
    ConsentFactory,
    ExchangeFactory,
    SchemeAccountFactory,
    SchemeAccountImageFactory,
    SchemeBalanceDetailsFactory,
    SchemeBundleAssociationFactory,
    SchemeCredentialAnswerFactory,
    SchemeCredentialQuestionFactory,
    SchemeFactory,
    SchemeImageFactory,
    UserConsentFactory,
)
from ubiquity.channel_vault import AESKeyNames
from ubiquity.models import AccountLinkStatus, PaymentCardSchemeEntry, SchemeAccountEntry
from ubiquity.tasks import async_join_journey_fetch_balance_and_update_status
from ubiquity.tests.factories import PaymentCardSchemeEntryFactory, SchemeAccountEntryFactory
from user.models import ClientApplication, ClientApplicationBundle
from user.tests.factories import ClientApplicationFactory, UserFactory


class TestSchemeAccountViews(GlobalMockAPITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.scheme = SchemeFactory()
        cls.scheme_image = SchemeImageFactory(scheme=cls.scheme)

        SchemeCredentialQuestionFactory(scheme=cls.scheme, type=USER_NAME, manual_question=True)

        secondary_question = SchemeCredentialQuestionFactory(
            scheme=cls.scheme, type=CARD_NUMBER, third_party_identifier=True, options=SchemeCredentialQuestion.LINK
        )
        password_question = SchemeCredentialQuestionFactory(
            scheme=cls.scheme, type=PASSWORD, options=SchemeCredentialQuestion.LINK_AND_JOIN
        )

        cls.scheme_account = SchemeAccountFactory(scheme=cls.scheme)
        cls.scheme_account_entry = SchemeAccountEntryFactory(scheme_account=cls.scheme_account)

        cls.user = cls.scheme_account_entry.user

        cls.scheme1 = SchemeFactory(card_number_regex=r"(^[0-9]{16})", card_number_prefix="", tier=Scheme.PLL)

        cls.scheme_account1 = SchemeAccountFactory(scheme=cls.scheme1)
        cls.scheme_account_entry1 = SchemeAccountEntryFactory(scheme_account=cls.scheme_account1)

        barcode_question = SchemeCredentialQuestionFactory(
            scheme=cls.scheme1, type=BARCODE, options=SchemeCredentialQuestion.LINK, third_party_identifier=True
        )
        SchemeCredentialQuestionFactory(scheme=cls.scheme1, type=CARD_NUMBER)

        cls.scheme.save()

        cls.scheme_account_answer_barcode = SchemeCredentialAnswerFactory(
            answer="9999888877776666",
            question=barcode_question,
            scheme_account_entry=cls.scheme_account_entry,
        )

        cls.scheme_account_answer_barcode = SchemeCredentialAnswerFactory(
            answer="9999888877776666",
            question=barcode_question,
            scheme_account_entry=cls.scheme_account_entry1,
        )

        cls.scheme_account_entry1_alt = SchemeAccountEntryFactory(scheme_account=cls.scheme_account1)

        cls.scheme_account_answer = SchemeCredentialAnswerFactory(
            question=cls.scheme.manual_question,
            scheme_account_entry=cls.scheme_account_entry,
        )
        cls.second_scheme_account_answer = SchemeCredentialAnswerFactory(
            question=secondary_question,
            scheme_account_entry=cls.scheme_account_entry,
        )

        cls.scheme_account_answer_password = SchemeCredentialAnswerFactory(
            answer="test_password",
            question=password_question,
            scheme_account_entry=cls.scheme_account_entry,
        )

        cls.consent = ConsentFactory.create(scheme=cls.scheme, slug=secrets.token_urlsafe())
        metadata1 = {"journey": JourneyTypes.LINK.value}
        metadata2 = {"journey": JourneyTypes.JOIN.value}
        cls.scheme_account_consent1 = UserConsentFactory(
            scheme_account=cls.scheme_account, metadata=metadata1, status=ConsentStatus.PENDING
        )
        cls.scheme_account_consent2 = UserConsentFactory(
            scheme_account=cls.scheme_account, metadata=metadata2, status=ConsentStatus.SUCCESS
        )

        cls.auth_service_headers = {"HTTP_AUTHORIZATION": "Token " + settings.SERVICE_API_KEY}

        cls.scheme_account_image = SchemeAccountImageFactory()

        cls.bink_client_app = ClientApplication.objects.get(client_id=settings.BINK_CLIENT_ID)
        cls.bink_user = UserFactory(client=cls.bink_client_app)

        cls.bundle = ClientApplicationBundle.objects.get(client=cls.bink_client_app, bundle_id="com.bink.wallet")
        # Need to add an active association since it was assumed no setting was enabled
        cls.scheme_bundle_association = SchemeBundleAssociationFactory(
            scheme=cls.scheme, bundle=cls.bundle, status=SchemeBundleAssociation.ACTIVE
        )

        cls.scheme_bundle_association1 = SchemeBundleAssociationFactory(
            scheme=cls.scheme1, bundle=cls.bundle, status=SchemeBundleAssociation.ACTIVE
        )

        cls.scheme_account_entry.update_scheme_account_key_credential_fields()
        cls.scheme_account_entry1.update_scheme_account_key_credential_fields()
        cls.auth_headers = {"HTTP_AUTHORIZATION": "Token " + cls.user.create_token(bundle_id=cls.bundle.bundle_id)}

        cls.scheme1_balance_details = SchemeBalanceDetailsFactory(scheme_id=cls.scheme1)

    @patch("scheme.models.requests.get")
    def test_analytics_when_balance_returns_configuration_error(self, mock_requests_get):
        class BalanceResponse:
            def __init__(self, status_code):
                self.status_code = status_code

        mock_requests_get.return_value = BalanceResponse(536)
        SchemeAccount._get_midas_balance(self.scheme_account, JourneyTypes.JOIN, self.scheme_account_entry)

    def test_scheme_account_query(self):
        resp = self.client.get(
            "/schemes/accounts/query?scheme__slug={}&user_set__id={}".format(self.scheme.slug, self.user.id),
            **self.auth_service_headers,
        )
        self.assertEqual(200, resp.status_code)
        self.assertEqual(resp.json()[0]["id"], self.scheme_account.id)

    def test_scheme_account_bad_query(self):
        resp = self.client.get("/schemes/accounts/query?scheme=what&user=no", **self.auth_service_headers)
        self.assertEqual(400, resp.status_code)

    def test_scheme_account_query_no_results(self):
        resp = self.client.get(
            "/schemes/accounts/query?scheme__slug=scheme-that-doesnt-exist", **self.auth_service_headers
        )
        self.assertEqual(200, resp.status_code)
        self.assertEqual(0, len(resp.json()))

    def test_get_scheme_account(self):
        self.scheme_account.alt_main_answer = self.scheme_account_answer.answer
        self.scheme_account.save()

        response = self.client.get("/schemes/accounts/{0}".format(self.scheme_account.id), **self.auth_headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(type(response.data), ReturnDict)
        self.assertEqual(response.data["id"], self.scheme_account.id)
        self.assertEqual(response.data["barcode"], "")
        self.assertEqual(response.data["card_label"], self.scheme_account_answer.answer)
        self.assertNotIn("is_deleted", response.data)
        self.assertEqual(response.data["scheme"]["id"], self.scheme.id)
        self.assertNotIn("card_number_prefix", response.data["scheme"])
        self.assertEqual(response.data["display_status"], AccountLinkStatus.ACTIVE)

        self.scheme_bundle_association.test_scheme = True
        self.scheme_bundle_association.save()
        response = self.client.get("/schemes/accounts/{0}".format(self.scheme_account.id), **self.auth_headers)
        self.assertEqual(response.status_code, 404)

        self.user.is_tester = True
        self.user.save()
        response = self.client.get("/schemes/accounts/{0}".format(self.scheme_account.id), **self.auth_headers)
        self.assertEqual(response.status_code, 200)

        self.scheme_bundle_association.test_scheme = False
        self.scheme_bundle_association.save()
        self.user.is_tester = False
        self.user.save()

    def test_service_delete_schemes_account(self):
        scheme_account = SchemeAccountFactory(scheme=self.scheme)
        SchemeAccountEntryFactory(scheme_account=scheme_account, user=self.user)
        SchemeAccountEntryFactory(scheme_account=scheme_account, user=self.bink_user)
        PaymentCardSchemeEntryFactory(scheme_account=scheme_account)

        response = self.client.delete(
            "/schemes/accounts/{0}/service".format(scheme_account.id), **self.auth_service_headers
        )
        deleted_scheme_account = SchemeAccount.all_objects.get(id=scheme_account.id)

        self.assertEqual(response.status_code, 204)
        self.assertTrue(deleted_scheme_account.is_deleted)
        self.assertFalse(SchemeAccountEntry.objects.filter(scheme_account=scheme_account))
        self.assertFalse(PaymentCardSchemeEntry.objects.filter(scheme_account=scheme_account))

    def test_service_delete_schemes_account_404(self):
        response = self.client.delete("/schemes/accounts/{0}/service".format(123456), **self.auth_service_headers)

        self.assertEqual(response.status_code, 404)

    @patch("scheme.views.async_join_journey_fetch_balance_and_update_status")
    def test_scheme_account_update_status_bink_user(self, *_):
        scheme_account = SchemeAccountFactory()
        scheme_account_entry = SchemeAccountEntryFactory(
            scheme_account=scheme_account, user=self.bink_user, link_status=AccountLinkStatus.ACTIVE
        )
        user_set = str(self.bink_user.id)

        data = {
            "status": AccountLinkStatus.MIDAS_UNREACHABLE,
            "journey": "join",
            "user_info": {"bink_user_id": user_set},
        }
        response = self.client.post(
            "/schemes/accounts/{}/status/".format(scheme_account.id), data, format="json", **self.auth_service_headers
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], scheme_account.id)
        self.assertEqual(response.data["status"], AccountLinkStatus.MIDAS_UNREACHABLE)
        scheme_account_entry.refresh_from_db()
        self.assertEqual(scheme_account_entry.link_status, AccountLinkStatus.MIDAS_UNREACHABLE)

    @patch("scheme.views.async_join_journey_fetch_balance_and_update_status")
    def test_scheme_account_update_status_404_missing_scheme_account(self, *_):
        missing_scheme_account_id = 999999
        user_set = str(self.bink_user.id)

        data = {
            "status": AccountLinkStatus.ACTIVE,
            "journey": "join",
            "user_info": {"bink_user_id": user_set},
        }
        response = self.client.post(
            "/schemes/accounts/{}/status/".format(missing_scheme_account_id),
            data,
            format="json",
            **self.auth_service_headers,
        )
        self.assertEqual(response.status_code, 404)

    @patch("scheme.views.async_join_journey_fetch_balance_and_update_status")
    def test_scheme_account_update_status_404_missing_entry(self, *_):
        scheme_account = SchemeAccountFactory()
        user_set = str(self.bink_user.id)

        data = {
            "status": AccountLinkStatus.ACTIVE,
            "journey": "join",
            "user_info": {"bink_user_id": user_set},
        }
        response = self.client.post(
            "/schemes/accounts/{}/status/".format(scheme_account.id), data, format="json", **self.auth_service_headers
        )
        self.assertEqual(response.status_code, 404)

    @patch("scheme.views.async_join_journey_fetch_balance_and_update_status")
    def test_scheme_account_update_status_ubiquity_user(self, *_):
        client_app = ClientApplicationFactory(name="barclays")
        scheme_account = SchemeAccountFactory()
        user = UserFactory(client=client_app)
        scheme_account_entry = SchemeAccountEntryFactory(
            scheme_account=scheme_account, user=user, link_status=AccountLinkStatus.ACTIVE
        )
        user_set = str(user.id)

        data = {
            "status": AccountLinkStatus.MIDAS_UNREACHABLE,
            "journey": "join",
            "user_info": {"user_set": user_set, "bink_user_id": user.id},
        }
        response = self.client.post(
            "/schemes/accounts/{}/status/".format(scheme_account.id), data, format="json", **self.auth_service_headers
        )
        scheme_account_entry.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], scheme_account.id)
        self.assertEqual(response.data["status"], AccountLinkStatus.MIDAS_UNREACHABLE)
        scheme_account.refresh_from_db()
        self.assertEqual(scheme_account_entry.link_status, AccountLinkStatus.MIDAS_UNREACHABLE)

    @patch("scheme.views.async_join_journey_fetch_balance_and_update_status")
    def test_scheme_account_update_status_populates_link_date(self, *_):
        client_app = ClientApplicationFactory(name="barclays")
        scheme_account = SchemeAccountFactory(link_date=None, join_date=None)
        user = UserFactory(client=client_app)
        scheme_account_entry = SchemeAccountEntryFactory(
            scheme_account=scheme_account, user=user, link_status=AccountLinkStatus.ACTIVE
        )
        user_set = str(user.id)

        data = {
            "status": AccountLinkStatus.ACTIVE,
            "journey": None,
            "user_info": {"user_set": user_set, "bink_user_id": user.id},
        }
        response = self.client.post(
            "/schemes/accounts/{}/status/".format(scheme_account.id), data, format="json", **self.auth_service_headers
        )
        scheme_account_entry.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], scheme_account.id)
        self.assertEqual(response.data["status"], AccountLinkStatus.ACTIVE)
        scheme_account.refresh_from_db()
        self.assertEqual(scheme_account_entry.link_status, AccountLinkStatus.ACTIVE)
        self.assertIsNotNone(scheme_account.link_date)
        self.assertIsNone(scheme_account.join_date)

    @patch("scheme.views.async_join_journey_fetch_balance_and_update_status")
    def test_scheme_account_update_status_join_callback(self, *_):
        scheme_account = SchemeAccountFactory()
        scheme_account_entry = SchemeAccountEntryFactory(
            scheme_account=scheme_account, user=self.bink_user, link_status=AccountLinkStatus.ACTIVE
        )

        # join callback has no user_set
        data = {
            "status": AccountLinkStatus.MIDAS_UNREACHABLE,
            "journey": "join",
            "user_info": {"bink_user_id": self.bink_user.id},
        }
        response = self.client.post(
            "/schemes/accounts/{}/status/".format(scheme_account.id), data, format="json", **self.auth_service_headers
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], scheme_account.id)
        self.assertEqual(response.data["status"], AccountLinkStatus.MIDAS_UNREACHABLE)
        scheme_account_entry.refresh_from_db()
        self.assertEqual(scheme_account_entry.link_status, AccountLinkStatus.MIDAS_UNREACHABLE)

    @patch("scheme.views.async_join_journey_fetch_balance_and_update_status")
    def test_scheme_account_update_status_multiple_values(self, *_):
        # todo: Checking with Merchant if we need to be able to do this still.

        entries = SchemeAccountEntry.objects.filter(scheme_account=self.scheme_account1)
        user_set = [str(entry.user.id) for entry in entries]
        self.assertTrue(len(user_set) > 1)

        entries = SchemeAccountEntry.objects.filter(scheme_account=self.scheme_account1)
        user_set = [str(entry.user.id) for entry in entries]
        self.assertTrue(len(user_set) > 1)

        user_info = {"user_set": ",".join(user_set), "bink_user_id": self.user.id}

        data = {"status": 9, "journey": "join", "user_info": user_info}
        response = self.client.post(
            "/schemes/accounts/{}/status/".format(self.scheme_account.id),
            data,
            format="json",
            **self.auth_service_headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], self.scheme_account.id)
        self.assertEqual(response.data["status"], 9)

    def test_scheme_account_update_status_bad(self):
        response = self.client.post(
            "/schemes/accounts/{}/status/".format(self.scheme_account.id),
            data={"status": 112, "journey": None, "user_info": {"bink_user_id": self.user.id}},
            format="json",
            **self.auth_service_headers,
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, ["Invalid status code sent."])

    @patch("scheme.views.async_join_journey_fetch_balance_and_update_status")
    def test_scheme_account_update_status_async_join_fail_deletes_main_answer(self, *_):
        client_app = ClientApplicationFactory(name="barclays")
        scheme_account = SchemeAccountFactory()
        user = UserFactory(client=client_app)
        scheme_account_entry = SchemeAccountEntryFactory(
            scheme_account=scheme_account, user=user, link_status=AccountLinkStatus.JOIN_ASYNC_IN_PROGRESS
        )
        user_set = str(user.id)

        scheme_account.alt_main_answer = "Somemainanswer"
        scheme_account.save()

        data = {
            "status": AccountLinkStatus.ENROL_FAILED,
            "journey": "join",
            "user_info": {"user_set": user_set, "bink_user_id": user.id},
        }
        response = self.client.post(
            reverse("change_account_status", args=[scheme_account.id]), data, format="json", **self.auth_service_headers
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], scheme_account.id)
        self.assertEqual(response.data["status"], AccountLinkStatus.ENROL_FAILED)

        scheme_account_entry.refresh_from_db()
        scheme_account.refresh_from_db()
        self.assertEqual(scheme_account.alt_main_answer, "")
        self.assertEqual(scheme_account_entry.link_status, AccountLinkStatus.ENROL_FAILED)

    @patch.object(SchemeAccount, "get_balance")
    def test_successful_join_gets_balance_and_sets_card_to_pending(self, *_):
        client_app = ClientApplicationFactory(name="barclays")
        scheme_account = SchemeAccountFactory()
        user = UserFactory(client=client_app)
        user_2 = UserFactory(client=client_app)
        scheme_account_entry = SchemeAccountEntryFactory(
            scheme_account=scheme_account, user=user, link_status=AccountLinkStatus.JOIN_ASYNC_IN_PROGRESS
        )
        scheme_account_entry_2 = SchemeAccountEntryFactory(
            scheme_account=scheme_account, user=user_2, link_status=AccountLinkStatus.ACTIVE
        )
        async_join_journey_fetch_balance_and_update_status(scheme_account.id, scheme_account_entry.id)

        scheme_account_entry.refresh_from_db()
        scheme_account_entry_2.refresh_from_db()
        self.assertEqual(scheme_account_entry.link_status, AccountLinkStatus.PENDING)
        self.assertEqual(scheme_account_entry_2.link_status, AccountLinkStatus.ACTIVE)
        self.assertTrue(scheme_account.get_balance.called)

    @patch("scheme.views.async_join_journey_fetch_balance_and_update_status")
    def test_scheme_account_update_join_acc_already_exists_fails(self, *_):
        client_app = ClientApplicationFactory(name="barclays")
        scheme_account = SchemeAccountFactory()
        user = UserFactory(client=client_app)
        scheme_account_entry = SchemeAccountEntryFactory(
            scheme_account=scheme_account, user=user, link_status=AccountLinkStatus.ACCOUNT_ALREADY_EXISTS
        )
        user_set = str(user.id)

        data = {
            "status": AccountLinkStatus.ACTIVE,
            "journey": "join",
            "user_info": {"user_set": user_set, "bink_user_id": user.id},
        }
        response = self.client.post(
            reverse("change_account_status", args=[scheme_account.id]), data, format="json", **self.auth_service_headers
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], scheme_account.id)
        self.assertEqual(response.data["status"], AccountLinkStatus.ACCOUNT_ALREADY_EXISTS)

        scheme_account.refresh_from_db()
        self.assertEqual(scheme_account_entry.link_status, AccountLinkStatus.ACCOUNT_ALREADY_EXISTS)

    def test_scheme_account_update_transactions(self):
        transactions = [
            {
                "id": 1,
                "scheme_account_id": self.scheme_account1.id,
                "created": "2020-05-15 12:08:10+00:00",
                "date": "2018-09-04 16:55:00+00:00",
                "description": "Test transaction: 2 items",
                "location": None,
                "points": -50.0,
                "value": None,
                "hash": "6fbbd14fc16964c314b4a0cc87db506f",
                "user_set": [self.user.id],
            },
            {
                "id": 2,
                "scheme_account_id": self.scheme_account1.id,
                "created": "2020-05-15 12:08:10+00:00",
                "date": "2018-09-04 07:35:10+00:00",
                "description": "Test transaction: 1 item",
                "location": None,
                "points": 10.0,
                "value": None,
                "hash": "f55cef56b2b3b47589299a14d88d2008",
                "user_set": [self.user.id],
            },
        ]

        serialized_transactions = [
            {
                "id": 1,
                "status": "active",
                "timestamp": 1536080100,
                "description": "Test transaction: 2 items",
                "amounts": [
                    {
                        "currency": self.scheme1_balance_details.currency,
                        "prefix": self.scheme1_balance_details.prefix,
                        "suffix": self.scheme1_balance_details.suffix,
                        "value": -50,
                    }
                ],
            },
            {
                "id": 2,
                "status": "active",
                "timestamp": 1536046510,
                "description": "Test transaction: 1 item",
                "amounts": [
                    {
                        "currency": self.scheme1_balance_details.currency,
                        "prefix": self.scheme1_balance_details.prefix,
                        "suffix": self.scheme1_balance_details.suffix,
                        "value": 10,
                    }
                ],
            },
        ]
        expected_resp = {"id": self.scheme_account1.id, "transactions": serialized_transactions}

        response = self.client.post(
            reverse("update_account_transactions", kwargs={"pk": self.scheme_account1.id}),
            data=json.dumps(transactions),
            format="json",
            **self.auth_service_headers,
        )

        self.scheme_account1.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, expected_resp)
        self.assertEqual(self.scheme_account1.transactions, serialized_transactions)

    def test_scheme_account_update_transactions_invalid_scheme_account_returns_error(self):
        transactions = []
        response = self.client.post(
            reverse("update_account_transactions", kwargs={"pk": 9999999999999}),
            data=json.dumps(transactions),
            format="json",
            **self.auth_service_headers,
        )
        self.assertEqual(response.status_code, 404)

    def test_scheme_account_update_transactions_invalid_transactions_returns_error(self):
        transactions = [{"id": 1, "scheme_account_id": self.scheme_account1.id, "points": -50.0, "value": None}]

        response = self.client.post(
            reverse("update_account_transactions", kwargs={"pk": self.scheme_account1.id}),
            data=json.dumps(transactions),
            format="json",
            **self.auth_service_headers,
        )

        self.assertEqual(response.status_code, 400)

    def test_scheme_accounts_active(self):
        # todo: Endpoint may be deprecated
        scheme_account = SchemeAccountFactory()
        SchemeAccountEntryFactory(user=self.user, scheme_account=scheme_account, link_status=AccountLinkStatus.ACTIVE)
        scheme_account_2 = SchemeAccountFactory()
        SchemeAccountEntryFactory(
            user=self.user, scheme_account=scheme_account_2, link_status=AccountLinkStatus.END_SITE_DOWN
        )
        response = self.client.get("/schemes/accounts/active", **self.auth_service_headers)

        self.assertEqual(response.status_code, 200)
        scheme_ids = [result["id"] for result in response.data["results"]]
        self.assertIsNone(response.data["next"])
        self.assertIn(scheme_account.id, scheme_ids)
        self.assertNotIn("credentials", response.data["results"][0])
        self.assertNotIn("scheme", response.data["results"][0])
        self.assertNotIn(scheme_account_2.id, scheme_ids)

    def test_system_retry_scheme_accounts(self):
        scheme = SchemeAccountFactory()
        scheme_2 = SchemeAccountFactory()
        SchemeAccountEntryFactory(link_status=AccountLinkStatus.RETRY_LIMIT_REACHED, scheme_account=scheme)
        SchemeAccountEntryFactory(link_status=AccountLinkStatus.ACTIVE, scheme_account=scheme_2)
        response = self.client.get("/schemes/accounts/system_retry", **self.auth_service_headers)
        scheme_ids = [result["id"] for result in response.data["results"]]

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["next"])
        self.assertIn(scheme.id, scheme_ids)
        self.assertNotIn(scheme_2.id, scheme_ids)

    def test_get_scheme_accounts_credentials(self):
        response = self.client.get(
            f"/schemes/accounts/{self.scheme_account.id}/credentials?bink_user_id={self.user.id}",
            **self.auth_service_headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("credentials", response.data)
        self.assertIn("scheme", response.data)
        self.assertIn("display_status", response.data)
        self.assertIn("status_name", response.data)
        self.assertIn("id", response.data)

    def test_get_scheme_accounts_credentials_user(self):
        response = self.client.get(
            f"/schemes/accounts/{self.scheme_account.id}/credentials?bink_user_id={self.user.id}", **self.auth_headers
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("id", response.data)

    def test_scheme_account_collect_credentials(self):
        self.assertEqual(
            self.scheme_account_entry._collect_credential_answers(),
            {
                "card_number": self.second_scheme_account_answer.answer,
                "password": "test_password",
                "username": self.scheme_account_answer.answer,
            },
        )

    def test_scheme_account_collect_credentials_with_merchant_identifier(self):
        third_question = SchemeCredentialQuestionFactory(
            scheme=self.scheme, type=TITLE, options=SchemeCredentialQuestion.MERCHANT_IDENTIFIER
        )
        SchemeCredentialAnswerFactory(
            question=third_question,
            answer="mr",
            scheme_account_entry=self.scheme_account_entry,
        )

        self.assertEqual(
            self.scheme_account_entry._collect_credential_answers(),
            {
                "card_number": self.second_scheme_account_answer.answer,
                "password": "test_password",
                "username": self.scheme_account_answer.answer,
                "title": "mr",
            },
        )

    def test_scheme_account_collect_pending_consents(self):
        consents = self.scheme_account.collect_pending_consents()

        self.assertEqual(len(consents), 1)
        expected_keys = {"id", "slug", "value", "created_on", "journey_type"}
        consent = consents[0]
        self.assertEqual(set(consent.keys()), expected_keys)
        self.assertEqual(consent["id"], self.scheme_account_consent1.id)

    def test_scheme_account_collect_pending_consents_no_data(self):
        self.assertEqual(self.scheme_account1.collect_pending_consents(), [])

    def test_scheme_account_third_party_identifier(self):
        self.assertEqual(self.scheme_account_entry.third_party_identifier, self.second_scheme_account_answer.answer)
        self.assertEqual(self.scheme_account_entry1.third_party_identifier, self.scheme_account_answer_barcode.answer)

    def test_scheme_account_encrypted_credentials(self):
        decrypted_credentials = json.loads(
            AESCipher(AESKeyNames.AES_KEY).decrypt(self.scheme_account_entry.credentials())
        )

        self.assertEqual(decrypted_credentials["card_number"], self.second_scheme_account_answer.answer)
        self.assertEqual(decrypted_credentials["password"], "test_password")
        self.assertEqual(decrypted_credentials["username"], self.scheme_account_answer.answer)

        consents = decrypted_credentials["consents"]
        self.assertEqual(len(consents), 1)
        expected_keys = {"id", "slug", "value", "created_on", "journey_type"}
        for consent in consents:
            self.assertEqual(set(consent.keys()), expected_keys)

    def test_scheme_account_encrypted_credentials_bad(self):
        scheme_account = SchemeAccountFactory(scheme=self.scheme)
        scheme_account_entry = SchemeAccountEntryFactory(scheme_account=scheme_account, user=self.user)
        encrypted_credentials = scheme_account_entry.credentials()
        self.assertIsNone(encrypted_credentials)
        self.assertEqual(scheme_account_entry.link_status, AccountLinkStatus.INCOMPLETE)

    def test_temporary_iceland_fix_ignores_credential_validation_for_iceland(self):
        scheme = SchemeFactory(slug="iceland-bonus-card")
        SchemeCredentialQuestionFactory(scheme=scheme, type=BARCODE, manual_question=True)
        SchemeCredentialQuestionFactory(scheme=scheme, type=PASSWORD, options=SchemeCredentialQuestion.LINK)
        scheme_account = SchemeAccountFactory(scheme=scheme)
        scheme_account_entry = SchemeAccountEntryFactory(scheme_account=scheme_account, user=self.user)

        self.assertIsNotNone(scheme_account_entry.credentials(), {})

    def test_temporary_iceland_fix_credential_validation_for_not_iceland(self):
        scheme = SchemeFactory(slug="not-iceland")
        SchemeCredentialQuestionFactory(scheme=scheme, type=BARCODE, manual_question=True)
        SchemeCredentialQuestionFactory(scheme=scheme, type=PASSWORD, options=SchemeCredentialQuestion.LINK)
        scheme_account = SchemeAccountFactory(scheme=scheme)
        scheme_account_entry = SchemeAccountEntryFactory(scheme_account=scheme_account, user=self.user)

        self.assertIsNone(scheme_account_entry.credentials())

    def test_scheme_account_answer_serializer(self):
        """
        If this test breaks you need to add the new credential to the SchemeAccountAnswerSerializer
        """
        expected_fields = dict(CREDENTIAL_TYPES)
        expected_fields["consents"] = None  # Add consents
        self.assertEqual(set(expected_fields.keys()), set(LinkSchemeSerializer._declared_fields.keys()))

    def all_statuses_correct(self, scheme_list):
        status_dict = dict(AccountLinkStatus.statuses())
        for scheme in scheme_list:
            scheme_status_codes = [int(s["status"]) for s in scheme["statuses"]]
            for status_code in status_dict:
                if status_code not in scheme_status_codes:
                    return False
        return True

    def test_register_join_endpoint_missing_credential_question(self):
        scheme = SchemeFactory()
        SchemeCredentialQuestionFactory(scheme=scheme, type=USER_NAME, options=SchemeCredentialQuestion.LINK_AND_JOIN)
        SchemeCredentialQuestionFactory(scheme=scheme, type=CARD_NUMBER)
        SchemeCredentialQuestionFactory(scheme=scheme, type=PASSWORD, options=SchemeCredentialQuestion.LINK_AND_JOIN)
        SchemeBundleAssociationFactory(scheme=scheme, bundle=self.bundle, status=SchemeBundleAssociation.ACTIVE)
        data = {"save_user_information": False, "order": 2, "password": "password"}
        resp = self.client.post("/schemes/{}/join".format(scheme.id), **self.auth_headers, data=data)

        self.assertEqual(resp.status_code, 400)
        json = resp.json()
        self.assertEqual(json, {"non_field_errors": ["username field required"]})

    def test_register_join_endpoint_scheme_has_no_join_questions(self):
        scheme = SchemeFactory()
        SchemeCredentialQuestionFactory(scheme=scheme, type=USER_NAME)
        SchemeCredentialQuestionFactory(scheme=scheme, type=CARD_NUMBER, options=SchemeCredentialQuestion.LINK)
        SchemeCredentialQuestionFactory(scheme=scheme, type=PASSWORD, options=SchemeCredentialQuestion.LINK)
        SchemeBundleAssociationFactory(scheme=scheme, bundle=self.bundle, status=SchemeBundleAssociation.ACTIVE)
        data = {"order": 2, "save_user_information": False, "username": "testbink", "password": "password"}
        resp = self.client.post("/schemes/{}/join".format(scheme.id), **self.auth_headers, data=data)

        self.assertEqual(resp.status_code, 400)
        json = resp.json()
        self.assertEqual(json, {"non_field_errors": ["No join questions found for scheme: {}".format(scheme.slug)]})

    def test_register_join_endpoint_account_already_created(self):
        scheme = SchemeFactory()
        SchemeCredentialQuestionFactory(scheme=scheme, type=USER_NAME, options=SchemeCredentialQuestion.LINK_AND_JOIN)
        SchemeCredentialQuestionFactory(scheme=scheme, type=CARD_NUMBER)
        SchemeCredentialQuestionFactory(scheme=scheme, type=PASSWORD, options=SchemeCredentialQuestion.JOIN)
        sa = SchemeAccountFactory(scheme_id=scheme.id)
        SchemeAccountEntryFactory(user=self.user, scheme_account=sa)
        SchemeBundleAssociationFactory(scheme=scheme, bundle=self.bundle, status=SchemeBundleAssociation.ACTIVE)
        data = {"save_user_information": False, "order": 2, "username": "testbink", "password": "password"}

        resp = self.client.post("/schemes/{}/join".format(scheme.id), **self.auth_headers, data=data)
        self.assertEqual(resp.status_code, 400)
        json = resp.json()
        self.assertTrue(json["non_field_errors"][0].startswith("You already have an account for this scheme"))

    def test_register_join_endpoint_link_join_question_mismatch(self):
        scheme = SchemeFactory()
        SchemeCredentialQuestionFactory(scheme=scheme, type=USER_NAME, options=SchemeCredentialQuestion.LINK_AND_JOIN)
        SchemeCredentialQuestionFactory(scheme=scheme, type=CARD_NUMBER, options=SchemeCredentialQuestion.LINK)
        SchemeCredentialQuestionFactory(scheme=scheme, type=PASSWORD, options=SchemeCredentialQuestion.JOIN)
        SchemeBundleAssociationFactory(scheme=scheme, bundle=self.bundle, status=SchemeBundleAssociation.ACTIVE)
        data = {"save_user_information": False, "order": 2, "username": "testbink", "password": "password"}
        resp = self.client.post("/schemes/{}/join".format(scheme.id), **self.auth_headers, data=data)
        self.assertEqual(resp.status_code, 400)
        json = resp.json()
        self.assertTrue(
            json["non_field_errors"][0].startswith(
                'Please convert all "Link" only credential' ' questions to "Join & Link"'
            )
        )

    @patch("api_messaging.midas_messaging.to_midas", autospec=True, return_value=MagicMock())
    def test_register_join_endpoint_create_scheme_account(self, _mock_message):
        scheme = SchemeFactory()
        link_question = SchemeCredentialQuestionFactory(
            scheme=scheme, type=USER_NAME, manual_question=True, options=SchemeCredentialQuestion.LINK_AND_JOIN
        )
        SchemeCredentialQuestionFactory(scheme=scheme, type=PASSWORD, options=SchemeCredentialQuestion.JOIN)
        SchemeCredentialQuestionFactory(scheme=scheme, type=BARCODE, options=SchemeCredentialQuestion.OPTIONAL_JOIN)
        SchemeBundleAssociationFactory(scheme=scheme, bundle=self.bundle, status=SchemeBundleAssociation.ACTIVE)

        test_reply = 1
        consent1 = ConsentFactory.create(scheme=scheme, journey=JourneyTypes.JOIN.value, order=1)

        data = {
            "save_user_information": False,
            "order": 2,
            "username": "testbink",
            "password": "password",
            "barcode": "barcode",
            "consents": [{"id": "{}".format(consent1.id), "value": test_reply}],
        }
        resp = self.client.post("/schemes/{}/join".format(scheme.id), **self.auth_headers, data=data, format="json")

        new_scheme_account = SchemeAccountEntry.objects.get(
            user=self.user, scheme_account__scheme=scheme
        ).scheme_account

        set_values = UserConsent.objects.filter(scheme_account=new_scheme_account).values()
        self.assertEqual(len(set_values), 1, "Incorrect number of consents found expected 1")
        for set_value in set_values:
            if set_value["slug"] == consent1.slug:
                self.assertEqual(set_value["value"], test_reply, "Incorrect Consent value set")
            else:
                self.assertTrue(False, "Consent not set")

        self.assertEqual(resp.status_code, 201)

        resp_json = resp.json()
        self.assertEqual(resp_json["scheme"], scheme.id)
        self.assertEqual(len(resp_json), len(data))  # not +1 to data since consents have been added
        scheme_account = SchemeAccount.objects.get(user_set__id=self.user.id, scheme_id=scheme.id)
        scheme_account_entry = SchemeAccountEntry.objects.get(user=self.user, scheme_account=scheme_account)
        self.assertEqual(resp_json["id"], scheme_account.id)
        self.assertEqual("Pending", scheme_account_entry.status_name)
        self.assertEqual(len(scheme_account_entry.schemeaccountcredentialanswer_set.all()), 1)
        self.assertTrue(scheme_account_entry.schemeaccountcredentialanswer_set.filter(question=link_question))

    @patch("api_messaging.midas_messaging.to_midas", autospec=True, return_value=MagicMock())
    def test_register_join_endpoint_optional_join_not_required(self, _mock_message):
        scheme = SchemeFactory()
        SchemeCredentialQuestionFactory(scheme=scheme, type=USER_NAME, options=SchemeCredentialQuestion.LINK_AND_JOIN)
        SchemeCredentialQuestionFactory(scheme=scheme, type=CARD_NUMBER)
        SchemeCredentialQuestionFactory(scheme=scheme, type=PASSWORD, options=SchemeCredentialQuestion.OPTIONAL_JOIN)
        SchemeBundleAssociationFactory(scheme=scheme, bundle=self.bundle, status=SchemeBundleAssociation.ACTIVE)
        data = {
            "save_user_information": False,
            "order": 2,
            "username": "testbink",
        }
        resp = self.client.post("/schemes/{}/join".format(scheme.id), **self.auth_headers, data=data)
        self.assertEqual(resp.status_code, 201)

    @patch("api_messaging.midas_messaging.to_midas", autospec=True, return_value=MagicMock())
    def test_register_join_endpoint_saves_user_profile(self, _mock_message):
        scheme = SchemeFactory()
        SchemeCredentialQuestionFactory(scheme=scheme, type=USER_NAME, options=SchemeCredentialQuestion.LINK_AND_JOIN)
        SchemeCredentialQuestionFactory(scheme=scheme, type=PASSWORD, options=SchemeCredentialQuestion.JOIN)
        SchemeCredentialQuestionFactory(
            scheme=scheme, type=EMAIL, manual_question=True, options=SchemeCredentialQuestion.JOIN
        )
        SchemeCredentialQuestionFactory(scheme=scheme, type=PHONE, options=SchemeCredentialQuestion.JOIN)
        SchemeCredentialQuestionFactory(scheme=scheme, type=TITLE, options=SchemeCredentialQuestion.JOIN)
        SchemeCredentialQuestionFactory(scheme=scheme, type=FIRST_NAME, options=SchemeCredentialQuestion.JOIN)
        SchemeCredentialQuestionFactory(scheme=scheme, type=LAST_NAME, options=SchemeCredentialQuestion.LINK_AND_JOIN)
        SchemeCredentialQuestionFactory(scheme=scheme, type=ADDRESS_1, options=SchemeCredentialQuestion.JOIN)
        SchemeCredentialQuestionFactory(scheme=scheme, type=ADDRESS_2, options=SchemeCredentialQuestion.JOIN)
        SchemeCredentialQuestionFactory(scheme=scheme, type=TOWN_CITY, options=SchemeCredentialQuestion.JOIN)
        SchemeBundleAssociationFactory(scheme=scheme, bundle=self.bundle, status=SchemeBundleAssociation.ACTIVE)

        phone_number = "01234567890"
        title = "mr"
        first_name = "bob"
        last_name = "test"
        address_1 = "1 ascot road"
        address_2 = "caversham"
        town_city = "ascot"
        data = {
            "save_user_information": True,
            "order": 2,
            "username": "testbink",
            "password": "password",
            "email": "test@testbink.com",
            "phone": phone_number,
            "title": title,
            "first_name": first_name,
            "last_name": last_name,
            "address_1": address_1,
            "address_2": address_2,
            "town_city": town_city,
        }
        resp = self.client.post("/schemes/{}/join".format(scheme.id), **self.auth_headers, data=data)
        self.assertEqual(resp.status_code, 201)

        user = SchemeAccountEntry.objects.filter(scheme_account__scheme=scheme, user=self.user).first().user
        user_profile = user.profile
        self.assertEqual(user_profile.phone, phone_number)
        self.assertEqual(user_profile.first_name, first_name)
        self.assertEqual(user_profile.last_name, last_name)
        self.assertEqual(user_profile.address_line_1, address_1)
        self.assertEqual(user_profile.address_line_2, address_2)
        self.assertEqual(user_profile.city, town_city)

    def test_update_user_consent(self):
        user_consent = UserConsentFactory(status=ConsentStatus.PENDING)
        data = {"status": ConsentStatus.SUCCESS.value}

        resp = self.client.put(
            "/schemes/user_consent/{}".format(user_consent.id), **self.auth_service_headers, data=data
        )
        self.assertEqual(resp.status_code, 200)
        user_consent.refresh_from_db()
        self.assertEqual(user_consent.status, ConsentStatus.SUCCESS)

    def test_update_user_consents_with_failed_deletes_consent(self):
        user_consent = UserConsentFactory(status=ConsentStatus.SUCCESS)
        data = {"status": ConsentStatus.FAILED.value}

        resp = self.client.put(
            "/schemes/user_consent/{}".format(user_consent.id), **self.auth_service_headers, data=data
        )
        self.assertEqual(resp.status_code, 400)
        user_consent.refresh_from_db()
        self.assertEqual(user_consent.status, ConsentStatus.SUCCESS)

    def test_update_user_consents_cant_delete_success_consent(self):
        user_consent = UserConsentFactory(status=ConsentStatus.SUCCESS)
        data = {"status": ConsentStatus.FAILED.value}

        resp = self.client.put(
            "/schemes/user_consent/{}".format(user_consent.id), **self.auth_service_headers, data=data
        )
        self.assertEqual(resp.status_code, 400)
        user_consent.refresh_from_db()
        self.assertEqual(user_consent.status, ConsentStatus.SUCCESS)

    def test_update_user_consents_cant_update_success_consent(self):
        user_consent = UserConsentFactory(status=ConsentStatus.SUCCESS)
        data = {"status": ConsentStatus.PENDING.value}

        resp = self.client.put(
            "/schemes/user_consent/{}".format(user_consent.id), **self.auth_service_headers, data=data
        )
        self.assertEqual(resp.status_code, 400)
        user_consent.refresh_from_db()
        self.assertEqual(user_consent.status, ConsentStatus.SUCCESS)


class TestSchemeAccountModel(GlobalMockAPITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.scheme = SchemeFactory()
        SchemeBalanceDetailsFactory(scheme_id=cls.scheme)

    def test_missing_credentials(self):
        scheme_account = SchemeAccountFactory()
        scheme_account_entry = SchemeAccountEntryFactory(scheme_account=scheme_account)
        SchemeCredentialQuestionFactory(
            scheme=scheme_account.scheme, type=PASSWORD, options=SchemeCredentialQuestion.LINK
        )
        SchemeCredentialQuestionFactory(scheme=scheme_account.scheme, type=CARD_NUMBER, scan_question=True)
        SchemeCredentialQuestionFactory(scheme=scheme_account.scheme, type=BARCODE, manual_question=True)
        SchemeCredentialQuestionFactory(
            scheme=scheme_account.scheme, type=TITLE, options=SchemeCredentialQuestion.MERCHANT_IDENTIFIER
        )
        self.assertEqual(scheme_account_entry.missing_credentials([]), {BARCODE, PASSWORD, CARD_NUMBER})
        self.assertFalse(scheme_account_entry.missing_credentials([CARD_NUMBER, PASSWORD]))
        self.assertFalse(scheme_account_entry.missing_credentials([BARCODE, PASSWORD]))
        self.assertEqual(scheme_account_entry.missing_credentials([PASSWORD]), {BARCODE, CARD_NUMBER})

    def test_missing_credentials_same_manual_and_scan(self):
        scheme_account = SchemeAccountFactory()
        scheme_account_entry = SchemeAccountEntryFactory(scheme_account=scheme_account)
        SchemeCredentialQuestionFactory(
            scheme=scheme_account.scheme, type=BARCODE, scan_question=True, manual_question=True
        )
        self.assertFalse(scheme_account_entry.missing_credentials([BARCODE]))
        self.assertEqual(scheme_account_entry.missing_credentials([]), {BARCODE})

    def test_missing_credentials_with_join_option_on_manual_question(self):
        scheme_account = SchemeAccountFactory()
        SchemeCredentialQuestionFactory(
            scheme=scheme_account.scheme, type=BARCODE, manual_question=True, options=SchemeCredentialQuestion.JOIN
        )
        SchemeCredentialQuestionFactory(
            scheme=scheme_account.scheme, type=CARD_NUMBER, scan_question=True, options=SchemeCredentialQuestion.NONE
        )
        SchemeCredentialQuestionFactory(
            scheme=scheme_account.scheme, type=PASSWORD, options=SchemeCredentialQuestion.LINK
        )
        scheme_account_entry = SchemeAccountEntryFactory(scheme_account=scheme_account)
        self.assertFalse(scheme_account_entry.missing_credentials([BARCODE, PASSWORD]))
        self.assertFalse(scheme_account_entry.missing_credentials([CARD_NUMBER, PASSWORD]))
        self.assertFalse(scheme_account_entry.missing_credentials([BARCODE, CARD_NUMBER, PASSWORD]))
        self.assertFalse(scheme_account_entry.missing_credentials([BARCODE, CARD_NUMBER, PASSWORD]))
        self.assertEqual(scheme_account_entry.missing_credentials([PASSWORD]), {BARCODE, CARD_NUMBER})

    def test_missing_credentials_with_join_option_on_manual_and_scan_question(self):
        scheme_account = SchemeAccountFactory()
        scheme_account_entry = SchemeAccountEntryFactory(scheme_account=scheme_account)
        SchemeCredentialQuestionFactory(
            scheme=scheme_account.scheme,
            type=BARCODE,
            manual_question=True,
            scan_question=True,
            options=SchemeCredentialQuestion.JOIN,
        )
        SchemeCredentialQuestionFactory(
            scheme=scheme_account.scheme, type=PASSWORD, options=SchemeCredentialQuestion.LINK
        )
        self.assertFalse(scheme_account_entry.missing_credentials([BARCODE, PASSWORD]))
        self.assertEqual(scheme_account_entry.missing_credentials([PASSWORD]), {BARCODE})
        self.assertEqual(scheme_account_entry.missing_credentials([BARCODE]), {PASSWORD})

    def test_credential_check_for_pending_scheme_account(self):
        scheme_account = SchemeAccountFactory()
        scheme_account_entry = SchemeAccountEntryFactory(
            scheme_account=scheme_account, link_status=AccountLinkStatus.PENDING
        )
        SchemeCredentialQuestionFactory(scheme=scheme_account.scheme, type=BARCODE, manual_question=True)
        scheme_account_entry.credentials()
        # We expect pending scheme accounts to be missing manual question
        self.assertNotEqual(scheme_account_entry.link_status, AccountLinkStatus.INCOMPLETE)

    def test_card_label_from_regex(self):
        scheme = SchemeFactory(card_number_regex="^[0-9]{3}([0-9]+)", card_number_prefix="98263000")
        scheme_account = SchemeAccountFactory(scheme=scheme, barcode="29930842203039")
        self.assertEqual(scheme_account.card_label, "9826300030842203039")

    def test_card_label_from_manual_answer(self):
        scheme = SchemeFactory()
        scheme_account = SchemeAccountFactory(scheme=scheme, alt_main_answer="frank@sdfg.com")
        self.assertEqual(scheme_account.card_label, "frank@sdfg.com")

    def test_card_label_from_barcode(self):
        scheme = SchemeFactory()
        scheme_account = SchemeAccountFactory(scheme=scheme, barcode="49932498")
        self.assertEqual(scheme_account.card_label, "49932498")

    def test_card_label_none(self):
        scheme = SchemeFactory()
        scheme_account = SchemeAccountFactory(scheme=scheme)
        self.assertIsNone(scheme_account.card_label)

    @patch.object(SchemeAccountEntry, "credentials", autospec=True, return_value=None)
    def test_get_balance_no_credentials(self, mock_credentials):
        entry = SchemeAccountEntryFactory()
        scheme_account = entry.scheme_account
        points, dw_event = scheme_account.get_balance(journey=JourneyTypes.UPDATE, scheme_account_entry=entry)

        self.assertIsNone(dw_event)
        self.assertIsNone(points)
        self.assertTrue(mock_credentials.called)

    @patch("requests.get", autospec=True, return_value=MagicMock())
    def test_get_balance(self, mock_request):
        mock_request.return_value.status_code = 200
        mock_request.return_value.json.return_value = {"points": 500}
        entry = SchemeAccountEntryFactory(scheme_account__scheme=self.scheme)
        scheme_account = entry.scheme_account
        points, dw_event = scheme_account.get_balance(journey=JourneyTypes.UPDATE, scheme_account_entry=entry)

        self.assertIsNone(dw_event)
        self.assertEqual(points[0]["value"], 500)
        self.assertEqual(entry.link_status, AccountLinkStatus.ACTIVE)

    @patch("requests.get", autospec=True, return_value=MagicMock())
    def test_get_balance_dw_event(self, mock_request):
        mock_request.return_value.status_code = 200
        mock_request.return_value.json.return_value = {"points": 500}
        entry = SchemeAccountEntryFactory(
            link_status=AccountLinkStatus.AUTH_PENDING, scheme_account__scheme=self.scheme
        )
        scheme_account = entry.scheme_account
        points, dw_event = scheme_account.get_balance(journey=JourneyTypes.UPDATE, scheme_account_entry=entry)

        self.assertTrue(dw_event[0])
        self.assertEqual(dw_event[1], AccountLinkStatus.AUTH_PENDING)
        self.assertEqual(points[0]["value"], 500)
        self.assertEqual(entry.link_status, AccountLinkStatus.ACTIVE)

    @patch("requests.get", autospec=True, side_effect=RequestConnectionError)
    def test_get_balance_connection_error(self, mock_request):
        entry = SchemeAccountEntryFactory()
        scheme_account = entry.scheme_account
        points, dw_event = scheme_account.get_balance(journey=JourneyTypes.UPDATE, scheme_account_entry=entry)

        self.assertIsNone(dw_event)
        self.assertIsNone(points)
        self.assertTrue(mock_request.called)
        self.assertEqual(entry.link_status, AccountLinkStatus.MIDAS_UNREACHABLE)

    @patch("requests.get", autospec=True, return_value=MagicMock())
    def test_get_balance_invalid_status(self, mock_request):
        invalid_status = 502
        mock_request.return_value.status_code = invalid_status
        scheme_account = SchemeAccountFactory()
        scheme_account_entry = SchemeAccountEntryFactory(
            scheme_account=scheme_account, link_status=AccountLinkStatus.PENDING
        )
        points, dw_event = scheme_account.get_balance(
            journey=JourneyTypes.UPDATE, scheme_account_entry=scheme_account_entry
        )

        # check this status hasn't been added to scheme account status
        self.assertNotIn(invalid_status, [status[0] for status in AccountLinkStatus.extended_statuses()])

        self.assertIsNone(dw_event)
        self.assertIsNone(points)
        self.assertTrue(mock_request.called)
        self.assertEqual(scheme_account_entry.link_status, AccountLinkStatus.UNKNOWN_ERROR)

    @patch("requests.get", autospec=True, return_value=MagicMock())
    def test_get_balance_link_limit_exceeded(self, mock_request):
        test_status = AccountLinkStatus.LINK_LIMIT_EXCEEDED
        mock_request.return_value.status_code = test_status
        scheme_account = SchemeAccountFactory()
        scheme_account_entry = SchemeAccountEntryFactory(scheme_account=scheme_account)
        points, dw_event = scheme_account.get_balance(
            journey=JourneyTypes.UPDATE, scheme_account_entry=scheme_account_entry
        )

        self.assertIsNone(dw_event)
        self.assertIsNone(points)
        self.assertTrue(mock_request.called)
        self.assertEqual(scheme_account_entry.link_status, test_status)
        self.assertEqual(scheme_account_entry.display_status, AccountLinkStatus.WALLET_ONLY)

    @patch("requests.get", autospec=True, return_value=MagicMock())
    def test_get_balance_card_not_registered(self, mock_request):
        test_status = AccountLinkStatus.CARD_NOT_REGISTERED
        mock_request.return_value.status_code = test_status
        scheme_account = SchemeAccountFactory()
        scheme_account_entry = SchemeAccountEntryFactory(scheme_account=scheme_account)
        points, dw_event = scheme_account.get_balance(
            journey=JourneyTypes.UPDATE, scheme_account_entry=scheme_account_entry
        )

        self.assertIsNone(dw_event)
        self.assertIsNone(points)
        self.assertTrue(mock_request.called)
        self.assertEqual(scheme_account_entry.link_status, test_status)
        self.assertEqual(scheme_account_entry.display_status, AccountLinkStatus.JOIN)

    @patch("requests.get", autospec=True, return_value=MagicMock())
    def test_get_balance_card_number_error(self, mock_request):
        test_status = AccountLinkStatus.CARD_NUMBER_ERROR
        mock_request.return_value.status_code = test_status
        scheme_account = SchemeAccountFactory()
        scheme_account_entry = SchemeAccountEntryFactory(scheme_account=scheme_account)
        points, dw_event = scheme_account.get_balance(
            journey=JourneyTypes.UPDATE, scheme_account_entry=scheme_account_entry
        )

        self.assertIsNone(dw_event)
        self.assertIsNone(points)
        self.assertTrue(mock_request.called)
        self.assertEqual(scheme_account_entry.link_status, test_status)
        self.assertEqual(scheme_account_entry.display_status, AccountLinkStatus.WALLET_ONLY)

    @patch("requests.get", autospec=True, return_value=MagicMock())
    def test_get_balance_general_error(self, mock_request):
        test_status = AccountLinkStatus.GENERAL_ERROR
        mock_request.return_value.status_code = test_status
        scheme_account = SchemeAccountFactory()
        scheme_account_entry = SchemeAccountEntryFactory(scheme_account=scheme_account)
        points, dw_event = scheme_account.get_balance(
            journey=JourneyTypes.UPDATE, scheme_account_entry=scheme_account_entry
        )

        self.assertIsNone(dw_event)
        self.assertIsNone(points)
        self.assertTrue(mock_request.called)
        self.assertEqual(scheme_account_entry.link_status, test_status)
        self.assertEqual(scheme_account_entry.display_status, AccountLinkStatus.WALLET_ONLY)

    @patch("requests.get", autospec=True, return_value=MagicMock())
    def test_get_balance_join_error(self, mock_request):
        test_status = AccountLinkStatus.JOIN_ERROR
        mock_request.return_value.status_code = test_status
        scheme_account = SchemeAccountFactory()
        scheme_account_entry = SchemeAccountEntryFactory(
            scheme_account=scheme_account, link_status=AccountLinkStatus.PENDING
        )

        points, dw_event = scheme_account.get_balance(
            journey=JourneyTypes.UPDATE, scheme_account_entry=scheme_account_entry
        )

        scheme_account_entry.refresh_from_db()

        self.assertIsNone(dw_event)
        self.assertIsNone(points)
        self.assertTrue(mock_request.called)
        self.assertEqual(scheme_account_entry.link_status, AccountLinkStatus.JOIN_ERROR)
        self.assertEqual(scheme_account_entry.display_status, AccountLinkStatus.WALLET_ONLY)

    @patch("requests.get", autospec=True, return_value=MagicMock())
    def test_get_balance_join_in_progress(self, mock_request):
        test_status = AccountLinkStatus.JOIN_IN_PROGRESS
        mock_request.return_value.status_code = test_status
        scheme_account = SchemeAccountFactory()
        scheme_account_entry = SchemeAccountEntryFactory(scheme_account=scheme_account)
        points, dw_event = scheme_account.get_balance(
            journey=JourneyTypes.UPDATE, scheme_account_entry=scheme_account_entry
        )

        self.assertIsNone(dw_event)
        self.assertIsNone(points)
        self.assertTrue(mock_request.called)
        self.assertEqual(scheme_account_entry.link_status, test_status)
        self.assertEqual(scheme_account_entry.display_status, AccountLinkStatus.WALLET_ONLY)

    @patch("requests.get", autospec=True, return_value=MagicMock())
    def test_ignore_get_balance_500_error(self, mock_request):
        test_status = AccountLinkStatus.TRIPPED_CAPTCHA
        mock_request.return_value.status_code = test_status
        scheme_account = SchemeAccountFactory()
        scheme_account_entry = SchemeAccountEntryFactory(
            scheme_account=scheme_account, link_status=AccountLinkStatus.ACTIVE
        )
        scheme_account.get_balance(journey=JourneyTypes.UPDATE, scheme_account_entry=scheme_account_entry)

        self.assertEqual(scheme_account_entry.link_status, AccountLinkStatus.ACTIVE)
        self.assertEqual(scheme_account_entry.display_status, AccountLinkStatus.ACTIVE)

    @patch("requests.get", autospec=True, return_value=MagicMock())
    def test_get_balance_500_error_preserve_scheme_account_error_status(self, mock_request):
        test_status = AccountLinkStatus.RESOURCE_LIMIT_REACHED
        mock_request.return_value.status_code = test_status
        scheme_account = SchemeAccountFactory()
        scheme_account_entry = SchemeAccountEntryFactory(
            scheme_account=scheme_account, link_status=AccountLinkStatus.TRIPPED_CAPTCHA
        )
        scheme_account.get_balance(journey=JourneyTypes.UPDATE, scheme_account_entry=scheme_account_entry)

        self.assertEqual(scheme_account_entry.link_status, AccountLinkStatus.RESOURCE_LIMIT_REACHED)
        self.assertEqual(scheme_account_entry.display_status, AccountLinkStatus.WALLET_ONLY)


class TestAccessTokens(GlobalMockAPITestCase):
    @classmethod
    def setUpTestData(cls):
        # Scheme Account 3
        cls.scheme_account_entry = SchemeAccountEntryFactory()
        cls.scheme_account = cls.scheme_account_entry.scheme_account

        question = SchemeCredentialQuestionFactory(
            type=CARD_NUMBER, scheme=cls.scheme_account.scheme, options=SchemeCredentialQuestion.LINK
        )

        cls.bink_client_app = ClientApplication.objects.get(client_id=settings.BINK_CLIENT_ID)
        cls.bundle = ClientApplicationBundle.objects.get(client=cls.bink_client_app, bundle_id="com.bink.wallet")

        cls.scheme = cls.scheme_account.scheme
        SchemeCredentialQuestionFactory(scheme=cls.scheme, type=USER_NAME, manual_question=True)

        cls.scheme_account_answer = SchemeCredentialAnswerFactory(
            question=question, scheme_account_entry=cls.scheme_account_entry
        )
        cls.user = cls.scheme_account_entry.user

        # Scheme Account 2
        cls.scheme_account_entry2 = SchemeAccountEntryFactory()
        cls.scheme_account2 = cls.scheme_account_entry2.scheme_account
        question_2 = SchemeCredentialQuestionFactory(type=CARD_NUMBER, scheme=cls.scheme_account2.scheme)

        cls.second_scheme_account_answer = SchemeCredentialAnswerFactory(
            question=question, scheme_account_entry=cls.scheme_account_entry2
        )
        cls.second_scheme_account_answer2 = SchemeCredentialAnswerFactory(
            question=question_2, scheme_account_entry=cls.scheme_account_entry2
        )

        cls.scheme2 = cls.scheme_account2.scheme
        SchemeCredentialQuestionFactory(scheme=cls.scheme2, type=USER_NAME, manual_question=True)

        cls.scheme_account_answer2 = SchemeCredentialAnswerFactory(
            question=cls.scheme2.manual_question,
            scheme_account_entry=cls.scheme_account_entry2,
        )
        cls.user2 = cls.scheme_account_entry2.user

        cls.scheme_bundle_association_1 = SchemeBundleAssociationFactory(
            scheme=cls.scheme, bundle=cls.bundle, status=SchemeBundleAssociation.ACTIVE
        )

        cls.scheme_bundle_association_2 = SchemeBundleAssociationFactory(
            scheme=cls.scheme2, bundle=cls.bundle, status=SchemeBundleAssociation.ACTIVE
        )

        cls.auth_headers = {"HTTP_AUTHORIZATION": "Token " + cls.user.create_token()}
        cls.auth_service_headers = {"HTTP_AUTHORIZATION": "Token " + settings.SERVICE_API_KEY}

    def setUp(self):
        self.test_scheme_acc_entry = SchemeAccountEntryFactory()
        self.test_user = self.test_scheme_acc_entry.user
        self.test_scheme_acc = self.test_scheme_acc_entry.scheme_account

    def test_retrieve_scheme_accounts(self):
        # GET Request
        response = self.client.get("/schemes/accounts/{}".format(self.scheme_account.id), **self.auth_headers)
        self.assertEqual(response.status_code, 200)
        response = self.client.get("/schemes/accounts/{}".format(self.scheme_account2.id), **self.auth_headers)
        self.assertEqual(response.status_code, 404)
        # DELETE Request
        response = self.client.delete("/schemes/accounts/{}".format(self.scheme_account.id), **self.auth_headers)
        self.assertEqual(response.status_code, 204)

        response = self.client.delete("/schemes/accounts/{}".format(self.scheme_account2.id), **self.auth_headers)
        self.assertEqual(response.status_code, 404)

        # Undo delete.
        self.scheme_account.is_deleted = False
        self.scheme_account.save()

    @patch.object(SchemeAccount, "_get_midas_balance")
    def test_get_scheme_accounts_credentials(self, mock_get_midas_balance):
        mock_get_midas_balance.return_value = (
            {
                "value": Decimal("10"),
                "points": Decimal("100"),
                "value_label": "$10",
                "reward_tier": 0,
                "balance": Decimal("20"),
                "is_stale": False,
            },
            AccountLinkStatus.ACTIVE,
            None,
        )
        # Test with service headers
        response = self.client.get(
            f"/schemes/accounts/{self.scheme_account.id}/credentials?bink_user_id={self.scheme_account_entry.user.id}",
            **self.auth_service_headers,
        )
        self.assertEqual(response.status_code, 200)
        response = self.client.get(
            f"/schemes/accounts/{self.scheme_account2.id}/credentials?bink_user_id="
            f"{self.scheme_account_entry2.user.id}",
            **self.auth_service_headers,
        )
        self.assertEqual(response.status_code, 200)
        # Test as standard user
        response = self.client.get(
            f"/schemes/accounts/{self.scheme_account.id}/credentials?bink_user_id="
            f"{self.scheme_account_entry.user.id}",
            **self.auth_headers,
        )
        self.assertEqual(response.status_code, 200)
        response = self.client.get(
            f"/schemes/accounts/{self.scheme_account2.id}/credentials?bink_user_id="
            f"{self.scheme_account_entry2.user.id}",
            **self.auth_headers,
        )
        self.assertEqual(response.status_code, 404)

    def test_update_or_create_primary_credentials_barcode_to_card_number(self):
        scheme = SchemeFactory(card_number_regex="^([0-9]{19})([0-9]{5})$")
        SchemeCredentialQuestionFactory(
            type=CARD_NUMBER, scheme=scheme, options=SchemeCredentialQuestion.JOIN, manual_question=True
        )

        SchemeCredentialQuestionFactory(
            type=BARCODE, scheme=scheme, options=SchemeCredentialQuestion.JOIN, scan_question=True
        )

        self.test_scheme_acc.scheme = scheme

        credentials = {"barcode": "633204003025524460012345"}
        new_credentials = self.test_scheme_acc_entry.update_or_create_primary_credentials(credentials)
        self.assertEqual(new_credentials, {"barcode": "633204003025524460012345", "card_number": "6332040030255244600"})

    def test_update_or_create_primary_credentials_card_number_to_barcode(self):
        scheme = SchemeFactory(barcode_regex="^([0-9]{19})([0-9]{5})$")
        SchemeCredentialQuestionFactory(
            type=CARD_NUMBER, scheme=scheme, options=SchemeCredentialQuestion.JOIN, manual_question=True
        )

        SchemeCredentialQuestionFactory(
            type=BARCODE, scheme=scheme, options=SchemeCredentialQuestion.JOIN, scan_question=True
        )

        self.test_scheme_acc.scheme = scheme

        credentials = {"card_number": "633204003025524460012345"}
        new_credentials = self.test_scheme_acc_entry.update_or_create_primary_credentials(credentials)
        self.assertEqual(new_credentials, {"card_number": "633204003025524460012345", "barcode": "6332040030255244600"})

    def test_update_or_create_primary_credentials_does_nothing_when_only_one_primary_cred_in_scheme(self):
        scheme = SchemeFactory(card_number_regex="^([0-9]{19})([0-9]{5})$")
        SchemeCredentialQuestionFactory(
            type=CARD_NUMBER, scheme=scheme, options=SchemeCredentialQuestion.JOIN, manual_question=True
        )

        self.test_scheme_acc.scheme = scheme

        credentials = {"barcode": "633204003025524460012345"}
        new_credentials = self.test_scheme_acc_entry.update_or_create_primary_credentials(credentials)
        self.assertEqual(new_credentials, {"barcode": "633204003025524460012345"})

    def test_update_or_create_primary_credentials_saves_non_regex_manual_question(self):
        scheme = SchemeFactory(card_number_regex="^([0-9]{19})([0-9]{5})$")
        question = SchemeCredentialQuestionFactory(
            type=EMAIL, scheme=scheme, options=SchemeCredentialQuestion.JOIN, manual_question=True
        )

        SchemeCredentialAnswerFactory(question=question, scheme_account_entry=self.test_scheme_acc_entry)
        self.test_scheme_acc.refresh_from_db()
        self.test_scheme_acc.scheme = scheme

        self.assertFalse(self.scheme_account.alt_main_answer)
        credentials = {"email": "testemail@testbink.com"}
        new_credentials = self.test_scheme_acc_entry.update_or_create_primary_credentials(credentials)
        self.assertEqual(new_credentials, {"email": "testemail@testbink.com"})
        self.assertEqual(
            "testemail@testbink.com", self.test_scheme_acc_entry.schemeaccountcredentialanswer_set.first().answer
        )


class TestSchemeAccountImages(GlobalMockAPITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.scheme_account_entry = SchemeAccountEntryFactory()
        cls.scheme_account = cls.scheme_account_entry.scheme_account
        cls.scheme_account_image = SchemeAccountImageFactory(image_type_code=2)
        cls.scheme_account_image.scheme_accounts.add(cls.scheme_account)

        cls.scheme_images = [
            SchemeImageFactory(image_type_code=1, scheme=cls.scheme_account.scheme),
            SchemeImageFactory(image_type_code=2, scheme=cls.scheme_account.scheme),
            SchemeImageFactory(image_type_code=3, scheme=cls.scheme_account.scheme),
        ]

        cls.user = cls.scheme_account_entry.user
        cls.auth_headers = {"HTTP_AUTHORIZATION": "Token " + cls.user.create_token()}

    def test_CSV_upload(self):
        csv_file = SimpleUploadedFile("file.csv", content=b"", content_type="text/csv")
        response = self.client.post(
            "/schemes/csv_upload", {"scheme": self.scheme_account.scheme.name, "emails": csv_file}, **self.auth_headers
        )
        self.assertEqual(response.status_code, 200)


class TestExchange(GlobalMockAPITestCase):
    def test_get_donor_schemes(self):
        host_scheme = self.create_scheme()
        donor_scheme_1 = self.create_scheme()
        donor_scheme_2 = self.create_scheme()

        user = UserFactory()

        self.create_scheme_account(host_scheme, user)
        self.create_scheme_account(donor_scheme_2, user)
        self.create_scheme_account(donor_scheme_1, user)

        ExchangeFactory(host_scheme=host_scheme, donor_scheme=donor_scheme_1)
        ExchangeFactory(host_scheme=host_scheme, donor_scheme=donor_scheme_2)

        auth_headers = {"HTTP_AUTHORIZATION": "Token " + settings.SERVICE_API_KEY}

        resp = self.client.get("/schemes/accounts/donor_schemes/{}/{}".format(host_scheme.id, user.id), **auth_headers)
        self.assertEqual(resp.status_code, 200)

        json = resp.json()
        self.assertEqual(type(json), list)
        self.assertIn("donor_scheme", json[0])
        self.assertIn("exchange_rate_donor", json[0])
        self.assertIn("exchange_rate_host", json[0])
        self.assertIn("host_scheme", json[0])
        self.assertIn("info_url", json[0])
        self.assertIn("tip_in_url", json[0])
        self.assertIn("transfer_max", json[0])
        self.assertIn("transfer_min", json[0])
        self.assertIn("transfer_multiple", json[0])
        self.assertIn("scheme_account_id", json[0])
        self.assertIn("name", json[0]["donor_scheme"])
        self.assertIn("point_name", json[0]["donor_scheme"])
        self.assertIn("name", json[0]["host_scheme"])
        self.assertIn("point_name", json[0]["host_scheme"])

    @staticmethod
    def create_scheme_account(host_scheme, user):
        scheme_account = SchemeAccountFactory(scheme=host_scheme)
        scheme_account_entry = SchemeAccountEntryFactory(user=user, scheme_account=scheme_account)
        SchemeCredentialAnswerFactory(scheme_account_entry=scheme_account_entry)
        return scheme_account

    @staticmethod
    def create_scheme():
        scheme = SchemeFactory()
        SchemeCredentialQuestionFactory(
            type=CARD_NUMBER, scheme=scheme, scan_question=True, options=SchemeCredentialQuestion.LINK
        )
        return scheme


class TestSchemeAccountCredentials(GlobalMockAPITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.scheme = SchemeFactory()
        cls.bink_client_app = ClientApplication.objects.get(client_id=settings.BINK_CLIENT_ID)
        cls.bundle = ClientApplicationBundle.objects.get(client=cls.bink_client_app, bundle_id="com.bink.wallet")

        SchemeCredentialQuestionFactory(scheme=cls.scheme, type=USER_NAME, manual_question=True)

        secondary_question = SchemeCredentialQuestionFactory(
            scheme=cls.scheme, type=CARD_NUMBER, options=SchemeCredentialQuestion.LINK
        )
        password_question = SchemeCredentialQuestionFactory(
            scheme=cls.scheme, type=PASSWORD, options=SchemeCredentialQuestion.LINK_AND_JOIN
        )

        # Create Schemes
        cls.scheme_account = SchemeAccountFactory(scheme=cls.scheme)
        cls.scheme_account2 = SchemeAccountFactory(scheme=cls.scheme)
        cls.scheme_account_no_answers = SchemeAccountFactory(scheme=cls.scheme)

        # Create SCEs
        cls.scheme_account_entry = SchemeAccountEntryFactory(scheme_account=cls.scheme_account)
        cls.scheme_account_entry2 = SchemeAccountEntryFactory(scheme_account=cls.scheme_account2)
        cls.scheme_account_entry_no_answers = SchemeAccountEntryFactory(scheme_account=cls.scheme_account_no_answers)

        # Create Answers: Scheme 1
        cls.scheme_account_answer = SchemeCredentialAnswerFactory(
            question=cls.scheme.manual_question,
            scheme_account_entry=cls.scheme_account_entry,
        )
        SchemeCredentialAnswerFactory(
            question=secondary_question,
            scheme_account_entry=cls.scheme_account_entry,
        )
        SchemeCredentialAnswerFactory(
            answer="testpassword",
            question=password_question,
            scheme_account_entry=cls.scheme_account_entry,
        )

        # Create Answers: Scheme 2

        SchemeCredentialAnswerFactory(
            answer="testpassword",
            question=password_question,
            scheme_account_entry=cls.scheme_account_entry2,
        )

        cls.scheme_bundle_association = SchemeBundleAssociationFactory(
            scheme=cls.scheme, bundle=cls.bundle, status=SchemeBundleAssociation.ACTIVE
        )

        cls.user = cls.scheme_account_entry.user
        cls.user2 = cls.scheme_account_entry2.user
        cls.user3 = cls.scheme_account_entry_no_answers.user

        cls.auth_headers = {"HTTP_AUTHORIZATION": "Token " + cls.user.create_token(), "HTTP_BINK_USER_ID": cls.user.id}
        cls.auth_headers2 = {
            "HTTP_AUTHORIZATION": "Token " + cls.user2.create_token(),
            "HTTP_BINK_USER_ID": cls.user2.id,
        }
        cls.auth_headers3 = {
            "HTTP_AUTHORIZATION": "Token " + cls.user3.create_token(),
            "HTTP_BINK_USER_ID": cls.user3.id,
        }

    def send_delete_credential_request(self, data):
        response = self.client.delete(
            f"/schemes/accounts/{self.scheme_account.id}/credentials",
            data=json.dumps(data),
            content_type="application/json",
            **self.auth_headers,
        )
        return response

    def test_update_new_and_existing_credentials(self):
        payload = {
            "card_number": "0123456",
            "password": "newpassword",
        }

        response = self.client.put(
            f"/schemes/accounts/{self.scheme_account2.id}/credentials",
            data=json.dumps(payload),
            content_type="application/json",
            **self.auth_headers2,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["updated"], ["card_number", "password"])

        credential_list = self.scheme_account_entry2.schemeaccountcredentialanswer_set.all()
        scheme_account_types = [answer.question.type for answer in credential_list]
        self.assertSequenceEqual(sorted(["card_number", "password"]), sorted(scheme_account_types))
        self.assertEqual(self.scheme_account_entry2._collect_credential_answers()["password"], "newpassword")

    def test_update_credentials_wrong_credential_type(self):
        payload = {"title": "mr"}

        response = self.client.put(
            f"/schemes/accounts/{self.scheme_account_no_answers.id}/credentials",
            data=json.dumps(payload),
            content_type="application/json",
            **self.auth_headers3,
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["non_field_errors"][0], "field(s) not found for scheme: title")
        credential_list = self.scheme_account_entry_no_answers.schemeaccountcredentialanswer_set.all()
        self.assertEqual(len(credential_list), 0)

    def test_update_credentials_bad_credential_type(self):
        payload = {"user_name": "user_name not username"}

        response = self.client.put(
            f"/schemes/accounts/{self.scheme_account_no_answers.id}/credentials",
            data=json.dumps(payload),
            content_type="application/json",
            **self.auth_headers3,
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["non_field_errors"][0], "field(s) not found for scheme: user_name")
        credential_list = self.scheme_account_entry_no_answers.schemeaccountcredentialanswer_set.all()
        self.assertEqual(len(credential_list), 0)

    def test_delete_credentials_by_type(self):
        response = self.send_delete_credential_request({"type_list": ["card_number", "username"]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["deleted"], "['card_number', 'username']")

        credential_list = self.scheme_account_entry.schemeaccountcredentialanswer_set.all()
        scheme_account_types = [answer.question.type for answer in credential_list]
        self.assertTrue("card_number" not in scheme_account_types)

    def test_delete_credentials_by_property(self):
        response = self.send_delete_credential_request({"property_list": ["link_questions"]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["deleted"], "['card_number', 'password']")

        credential_list = self.scheme_account_entry.schemeaccountcredentialanswer_set.all()
        scheme_account_types = [answer.question.type for answer in credential_list]
        self.assertTrue("card_number" not in scheme_account_types)
        self.assertTrue("password" not in scheme_account_types)

    def test_delete_all_credentials(self):
        credential_list = self.scheme_account_entry.schemeaccountcredentialanswer_set.all()
        self.assertEqual(len(credential_list), 3)
        response = self.send_delete_credential_request({"all": True})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["deleted"], "['card_number', 'password', 'username']")

        new_credential_list = self.scheme_account_entry.schemeaccountcredentialanswer_set.all()
        self.assertEqual(len(new_credential_list), 0)

    def test_delete_credentials_invalid_request(self):
        response = self.send_delete_credential_request({"all": "not a boolean"})
        self.assertEqual(response.status_code, 400)
        self.assertTrue("Must be a valid boolean" in str(response.json()))

        credential_list = self.scheme_account_entry.schemeaccountcredentialanswer_set.all()
        self.assertEqual(len(credential_list), 3)

    def test_delete_credentials_wrong_credential(self):
        response = self.client.delete(
            f"/schemes/accounts/{self.scheme_account2.id}/credentials",
            data={"type_list": ["card_number", "password"]},
            **self.auth_headers2,
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(response.json()["message"].startswith("No answers found for: card_number"))

        credential_list = self.scheme_account_entry.schemeaccountcredentialanswer_set.all()
        self.assertEqual(len(credential_list), 3)

    def test_delete_credentials_with_scheme_account_without_credentials(self):
        response = self.client.delete(
            f"/schemes/accounts/{self.scheme_account_no_answers.id}/credentials",
            data={"all": True},
            **self.auth_headers3,
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(response.json()["message"].startswith("No answers found"))
