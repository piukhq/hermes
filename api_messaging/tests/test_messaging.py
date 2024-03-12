from unittest.mock import patch

import arrow

from api_messaging import angelia_background, route
from api_messaging.angelia_background import save_credential_answers
from api_messaging.exceptions import InvalidMessagePath
from history.utils import GlobalMockAPITestCase
from payment_card.models import PaymentCardAccount
from payment_card.tests.factories import PaymentCardAccountFactory
from scheme.credentials import CARD_NUMBER, LAST_NAME, POSTCODE
from scheme.models import SchemeAccountCredentialAnswer
from scheme.tests.factories import SchemeAccountFactory, SchemeCredentialQuestionFactory
from ubiquity.models import (
    PaymentCardAccountEntry,
    PaymentCardSchemeEntry,
    PllUserAssociation,
    WalletPLLSlug,
    WalletPLLStatus,
)
from ubiquity.tests.factories import PaymentCardAccountEntryFactory, SchemeAccountEntryFactory
from user.models import CustomUser
from user.tests.factories import UserFactory


class TestPaymentAccountMessaging(GlobalMockAPITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.payment_card_account_entry = PaymentCardAccountEntryFactory(
            payment_card_account__psp_token="test_token", payment_card_account__status=PaymentCardAccount.ACTIVE
        )
        cls.scheme_account = SchemeAccountFactory()
        cls.scheme_account.user_set.add(cls.payment_card_account_entry.user)
        cls.post_payment_account_message = {
            "utc_adjusted": arrow.utcnow().isoformat(),
            "payment_account_id": cls.payment_card_account_entry.payment_card_account.id,
            "user_id": cls.payment_card_account_entry.user.id,
            "channel_slug": "com.bink.wallet",
            "created": True,
            "auto_link": False,
        }
        cls.post_payment_account_auto_link_message = {
            "utc_adjusted": arrow.utcnow().isoformat(),
            "payment_account_id": cls.payment_card_account_entry.payment_card_account.id,
            "user_id": cls.payment_card_account_entry.user.id,
            "channel_slug": "com.bink.wallet",
            "created": False,
            "auto_link": True,
        }
        cls.delete_payment_account_message = {
            "utc_adjusted": arrow.utcnow().isoformat(),
            "payment_account_id": cls.payment_card_account_entry.payment_card_account.id,
            "user_id": cls.payment_card_account_entry.user.id,
            "channel_slug": "com.bink.wallet",
        }
        cls.post_payment_account_headers = {"X-http-path": "post_payment_account"}
        cls.delete_payment_account_headers = {"X-http-path": "delete_payment_account"}
        cls.x_azure_ref_headers = {"X-azure-ref": "x_azure_ref"}
        cls.fail_headers = {"X-http-path": "failing_test"}

    @patch("api_messaging.angelia_background.post_payment_account")
    def test_post_routing(self, mock_post_payment_account):
        route.route_message(self.post_payment_account_headers, self.post_payment_account_message)

        self.assertTrue(mock_post_payment_account.called)

    @patch("api_messaging.angelia_background.delete_payment_account")
    def test_delete_routing(self, mock_delete_payment_account):
        route.route_message(self.delete_payment_account_headers, self.delete_payment_account_message)

        self.assertTrue(mock_delete_payment_account.called)

    def test_failed_route(self):
        with self.assertRaises(InvalidMessagePath):
            route.route_message(self.fail_headers, self.post_payment_account_message)

    @patch("payment_card.metis.enrol_new_payment_card")
    def test_process_post_payment_card_message(self, mock_metis_enrol):
        angelia_background.post_payment_account(self.post_payment_account_message, self.x_azure_ref_headers)
        self.assertTrue(mock_metis_enrol.called)

    @patch("payment_card.metis.enrol_new_payment_card")
    def test_process_post_payment_card_message_auto_link_created_false(self, mock_metis_enrol):
        angelia_background.post_payment_account(self.post_payment_account_auto_link_message, self.x_azure_ref_headers)
        self.assertFalse(mock_metis_enrol.called)
        links = PaymentCardSchemeEntry.objects.filter(
            scheme_account=self.scheme_account,
            payment_card_account=self.payment_card_account_entry.payment_card_account,
        ).all()
        self.assertEqual(len(links), 1)
        user_pll = PllUserAssociation.objects.filter(pll=links[0], user=self.payment_card_account_entry.user)
        self.assertEqual(len(user_pll), 1)
        self.assertEqual(user_pll[0].slug, WalletPLLSlug.LOYALTY_CARD_PENDING.value)
        self.assertEqual(user_pll[0].state, WalletPLLStatus.PENDING)
        self.assertEqual(links[0].active_link, False)

    @patch("payment_card.metis.delete_payment_card")
    def test_process_delete_payment_account_deleted(self, metis_delete_payment_card):
        objects_pre = PaymentCardAccountEntry.objects.filter(id=self.payment_card_account_entry.id).count()
        angelia_background.delete_payment_account(self.delete_payment_account_message, self.x_azure_ref_headers)
        objects_post = PaymentCardAccountEntry.objects.filter(id=self.payment_card_account_entry.id).count()

        self.assertEqual(objects_pre, 1)
        self.assertLess(objects_post, objects_pre)
        self.assertTrue(metis_delete_payment_card.called)


class TestLoyaltyCardMessaging(GlobalMockAPITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.scheme_account = SchemeAccountFactory()
        cls.scheme_account_entry = SchemeAccountEntryFactory(scheme_account=cls.scheme_account)
        cls.payment_account = PaymentCardAccountFactory()
        cls.payment_account_entry = PaymentCardAccountEntryFactory(
            payment_card_account=cls.payment_account,
            user=cls.scheme_account_entry.user,
            payment_card_account__psp_token="test_token",
            payment_card_account__status=PaymentCardAccount.ACTIVE,
        )

        SchemeCredentialQuestionFactory(scheme=cls.scheme_account.scheme, type=CARD_NUMBER)
        SchemeCredentialQuestionFactory(scheme=cls.scheme_account.scheme, type=LAST_NAME)
        SchemeCredentialQuestionFactory(scheme=cls.scheme_account.scheme, type=POSTCODE)

        cls.auth_fields = [
            {"credential_slug": "last_name", "value": "Jones"},
            {"credential_slug": "postcode", "value": "RGB 114"},
        ]
        cls.consents = [{"id": 15, "value": "true"}]
        cls.creds_for_refactor = [
            {"credential_slug": "postcode", "value": "GU552RH"},
            {"credential_slug": "last_name", "value": "Bond"},
            {"credential_slug": "email", "value": "007@mi5.com"},
        ]
        cls.loyalty_card_auth_autolink_message = {
            "utc_adjusted": arrow.utcnow().isoformat(),
            "loyalty_card_id": cls.scheme_account.id,
            "user_id": cls.scheme_account_entry.user.id,
            "entry_id": cls.scheme_account_entry.id,
            "channel_slug": "com.bink.wallet",
            "auto_link": True,
            "primary_auth": True,
            "authorise_fields": cls.auth_fields,
        }
        cls.loyalty_card_auth_no_autolink_message = {
            "utc_adjusted": arrow.utcnow().isoformat(),
            "loyalty_card_id": cls.scheme_account.id,
            "user_id": cls.scheme_account_entry.user.id,
            "entry_id": cls.scheme_account_entry.id,
            "channel_slug": "com.bink.wallet",
            "auto_link": False,
            "primary_auth": False,
            "authorise_fields": cls.auth_fields,
        }

        cls.loyalty_card_register_message = {
            "utc_adjusted": arrow.utcnow().isoformat(),
            "loyalty_card_id": cls.scheme_account.id,
            "user_id": cls.scheme_account_entry.user.id,
            "entry_id": cls.scheme_account_entry.id,
            "channel_slug": "com.bink.wallet",
            "auto_link": True,
            "loyalty_plan_id": cls.scheme_account.scheme.id,
            "add_fields": [{"credential_slug": "card_number", "value": "76389246123642384"}],
            "register_fields": [{"credential_slug": "postcode", "value": "GU552RH"}],
            "consents": cls.consents,
        }

        cls.loyalty_card_join_message = {
            "utc_adjusted": arrow.utcnow().isoformat(),
            "loyalty_card_id": cls.scheme_account.id,
            "user_id": cls.scheme_account_entry.user.id,
            "channel_slug": "com.bink.wallet",
            "auto_link": True,
            "loyalty_plan_id": cls.scheme_account.scheme.id,
            "join_fields": [{"credential_slug": "postcode", "value": "GU552RH"}],
            "consents": cls.consents,
        }

        cls.delete_loyalty_card_message = {
            "utc_adjusted": arrow.utcnow().isoformat(),
            "loyalty_card_id": cls.scheme_account.id,
            "user_id": cls.scheme_account_entry.user.id,
            "channel_slug": "com.bink.wallet",
            "auto_link": False,
            "created": True,
            "loyalty_plan_id": cls.scheme_account.scheme.id,
        }

        cls.loyalty_card_authorise_headers = {"X-http-path": "loyalty_card_authorise"}
        cls.loyalty_card_add_and_authorise_headers = {"X-http-path": "loyalty_card_authorise"}
        cls.loyalty_card_register_headers = {"X-http-path": "loyalty_card_register"}
        cls.x_azure_ref_headers = {"X-azure-ref": "x_azure_ref"}
        cls.fail_headers = {"X-http-path": "failing_test"}

    @patch("api_messaging.angelia_background.loyalty_card_authorise")
    def loyalty_card_auth_routing(self, mock_loyalty_card_authorise):
        route.route_message(self.loyalty_card_authorise_headers, self.loyalty_card_auth_autolink_message)

        self.assertTrue(mock_loyalty_card_authorise.called)

    @patch("api_messaging.angelia_background.loyalty_card_authorise")
    def loyalty_card_add_and_authorise_routing(self, mock_loyalty_card_authorise):
        route.route_message(self.loyalty_card_add_and_authorise_headers, self.loyalty_card_auth_autolink_message)

        self.assertTrue(mock_loyalty_card_authorise.called)

    @patch("api_messaging.angelia_background.loyalty_card_register")
    def loyalty_card_register_routing(self, mock_loyalty_card_register):
        route.route_message(self.loyalty_card_register_headers, self.loyalty_card_register_message)

        self.assertTrue(mock_loyalty_card_register.called)

    def test_failed_route(self):
        with self.assertRaises(InvalidMessagePath):
            route.route_message(self.fail_headers, self.loyalty_card_auth_autolink_message)

    @patch("api_messaging.angelia_background.async_link")
    def test_loyalty_card_authorise_async_link(self, mock_async_link):
        """Tests AUTH routing for an existing loyalty card with auto-linking"""
        angelia_background.loyalty_card_add_authorise(self.loyalty_card_auth_autolink_message, self.x_azure_ref_headers)
        self.assertTrue(mock_async_link.called)
        params = mock_async_link.call_args.kwargs
        to_link = params.get("payment_cards_to_link", [])
        self.assertEqual(len(to_link), 1)

    @patch("api_messaging.angelia_background.async_link")
    def test_loyalty_card_authorise_no_autolink(self, mock_async_link):
        """Tests AUTH routing for an existing loyalty card without auto-linking"""

        angelia_background.loyalty_card_add_authorise(
            self.loyalty_card_auth_no_autolink_message, self.x_azure_ref_headers
        )
        self.assertTrue(mock_async_link.called)
        params = mock_async_link.call_args.kwargs
        to_link = params.get("payment_cards_to_link", [])
        self.assertEqual(len(to_link), 0)

    @patch("api_messaging.angelia_background.MembershipCardView.handle_registration_route")
    def test_loyalty_card_register_journey(self, mock_handle_registration):
        """Tests routing for Registering a loyalty card"""
        angelia_background.loyalty_card_register(self.loyalty_card_register_message, self.x_azure_ref_headers)
        self.assertTrue(mock_handle_registration.called)
        # Should ideally check linking

    @patch("api_messaging.angelia_background.async_join")
    def test_loyalty_card_join_journey(self, mock_async_join):
        """Tests Join routing for a loyalty card"""

        angelia_background.loyalty_card_join(self.loyalty_card_join_message, self.x_azure_ref_headers)

        self.assertTrue(mock_async_join.called)

    @patch("api_messaging.angelia_background.deleted_membership_card_cleanup")
    def test_delete_loyalty_card_journey(self, mock_deleted_card_cleanup):
        """Tests successful routing for a DELETE loyalty card journey."""

        angelia_background.delete_loyalty_card(self.delete_loyalty_card_message, self.x_azure_ref_headers)

        self.assertTrue(mock_deleted_card_cleanup.called)

    def test_credentials_to_key_pairs(self):
        """Tests refactoring of credentials from Angelia to Ubiquity format."""

        creds = angelia_background.credentials_to_key_pairs(self.creds_for_refactor)

        self.assertEqual({"postcode": "GU552RH", "last_name": "Bond", "email": "007@mi5.com"}, creds)

    def test_save_credential_answers(self):
        """Tests saving credential answers received from Angelia."""
        answers = SchemeAccountCredentialAnswer.objects.filter(scheme_account_entry=self.scheme_account_entry)
        self.assertEqual(0, answers.count())

        save_credential_answers(self.scheme_account_entry, credentials=self.auth_fields)

        self.assertEqual(2, answers.count())

        question_types = (answer.question.type for answer in answers)
        for expected_q_type in ("last_name", "postcode"):
            self.assertIn(expected_q_type, question_types)


class TestUserMessaging(GlobalMockAPITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = UserFactory()
        cls.delete_user_headers = {"X-http-path": "delete_user"}
        cls.delete_user_message = {
            "utc_adjusted": arrow.utcnow().isoformat(),
            "user_id": cls.user.id,
            "channel_slug": "com.bink.wallet",
        }

    @patch("api_messaging.angelia_background.deleted_service_cleanup")
    def test_delete_user(self, mock_delete_cleanup):
        user_pre = CustomUser.objects.filter(id=self.user.id, is_active=True)

        self.assertTrue(user_pre)

        route.route_message(self.delete_user_headers, self.delete_user_message)

        user_post = CustomUser.objects.filter(id=self.delete_user_message["user_id"], is_active=True)

        self.assertFalse(user_post)
        self.assertTrue(mock_delete_cleanup.called)
