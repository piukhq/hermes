from unittest.mock import patch

from api_messaging import angelia_background, route
from api_messaging.exceptions import InvalidMessagePath
from history.utils import GlobalMockAPITestCase
from payment_card.models import PaymentCardAccount
from payment_card.tests.factories import PaymentCardAccountFactory
from scheme.tests.factories import SchemeAccountFactory
from ubiquity.tests.factories import PaymentCardAccountEntryFactory, SchemeAccountEntryFactory


class TestPaymentAccountMessaging(GlobalMockAPITestCase):

    @classmethod
    def setUpTestData(cls):
        cls.payment_card_account_entry = PaymentCardAccountEntryFactory(
            payment_card_account__psp_token="test_token",
            payment_card_account__status=PaymentCardAccount.ACTIVE
        )
        cls.scheme_account = SchemeAccountFactory()
        cls.scheme_account.user_set.add(cls.payment_card_account_entry.user)
        cls.post_payment_account_message = {
            "payment_account_id": cls.payment_card_account_entry.payment_card_account.id,
            "user_id": cls.payment_card_account_entry.user.id,
            "channel_id": "com.bink.wallet",
            "created": True,
            "auto_link": False,
        }
        cls.post_payment_account_auto_link_message = {
            "payment_account_id": cls.payment_card_account_entry.payment_card_account.id,
            "user_id": cls.payment_card_account_entry.user.id,
            "channel_id": "com.bink.wallet",
            "created": False,
            "auto_link": True,
        }
        cls.delete_payment_account_message = {
            "payment_account_id": cls.payment_card_account_entry.payment_card_account.id,
            "user_id": cls.payment_card_account_entry.user.id,
            "channel_id": "com.bink.wallet",
        }
        cls.post_payment_account_headers = {"X-http-path": "post_payment_account"}
        cls.delete_payment_account_headers = {"X-http-path": "delete_payment_account"}
        cls.fail_headers = {"X-http-path": "failing_test"}

    @patch('api_messaging.angelia_background.post_payment_account')
    def test_post_routing(self, mock_post_payment_account):
        route.route_message(self.post_payment_account_headers, self.post_payment_account_message)

        self.assertTrue(mock_post_payment_account.called)

    @patch('api_messaging.angelia_background.delete_payment_account')
    def test_delete_routing(self, mock_delete_payment_account):
        route.route_message(self.delete_payment_account_headers, self.delete_payment_account_message)

        self.assertTrue(mock_delete_payment_account.called)

    def test_failed_route(self):
        with self.assertRaises(InvalidMessagePath):
            route.route_message(self.fail_headers, self.post_payment_account_message)

    @patch('payment_card.metis.enrol_new_payment_card')
    def test_process_post_payment_card_message(self, mock_metis_enrol):
        angelia_background.post_payment_account(self.post_payment_account_message)

        self.assertTrue(mock_metis_enrol.called)

    @patch('ubiquity.views.AutoLinkOnCreationMixin.auto_link_to_membership_cards')
    def test_process_post_payment_card_message_auto_link(self, mock_auto_link):
        angelia_background.post_payment_account(self.post_payment_account_auto_link_message)

        self.payment_card_account_entry.refresh_from_db()

        self.assertIsNot(self.payment_card_account_entry.payment_card_account.pll_links, [])
        self.assertTrue(mock_auto_link.called)

    @patch('payment_card.metis.delete_payment_card')
    def test_process_delete_payment_account_deleted(self, metis_delete_payment_card):
        objects_pre = PaymentCardAccount.objects.filter(id=self.payment_card_account_entry.id).count()

        angelia_background.delete_payment_account(self.delete_payment_account_message)

        objects_post = PaymentCardAccount.objects.filter(id=self.payment_card_account_entry.id).count()

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
            payment_card_account__status=PaymentCardAccount.ACTIVE
            )
        cls.auth_fields = [{"credential_slug": "last_name", "value": "Jones"},
                           {"credential_slug": "postcode", "value": "RGB 114"}]
        cls.consents = [{"id": 15, "value": "true"}]
        cls.loyalty_card_auth_autolink_created_message = {
            "loyalty_card_id": cls.scheme_account_entry.id,
            "user_id": cls.scheme_account_entry.user.id,
            "channel": "com.bink.wallet",
            "auto_link": True,
            "created": True,
            "authorise_fields": cls.auth_fields
        }
        cls.loyalty_card_auth_autolink_existing_message = {
            "loyalty_card_id": cls.scheme_account_entry.id,
            "user_id": cls.scheme_account_entry.user.id,
            "channel": "com.bink.wallet",
            "auto_link": True,
            "created": False,
            "authorise_fields": cls.auth_fields
        }
        cls.loyalty_card_auth_no_autolink_existing_message = {
            "loyalty_card_id": cls.scheme_account_entry.id,
            "user_id": cls.scheme_account_entry.user.id,
            "channel": "com.bink.wallet",
            "auto_link": False,
            "created": False,
            "authorise_fields": cls.auth_fields
        }

        cls.loyalty_card_register_message = {
            "loyalty_card_id": cls.scheme_account_entry.id,
            "user_id": cls.scheme_account_entry.user.id,
            "channel": "com.bink.wallet",
            "auto_link": False,
            "created": False,
            "loyalty_plan_id": cls.scheme_account.id,
            "register_fields": [{"credential_slug": "postcode", "value": "GU552RH"}],
            "consents": cls.consents
        }

        cls.delete_loyalty_card_message = {
            "loyalty_card_id": cls.scheme_account_entry.id,
            "user_id": cls.scheme_account_entry.user.id,
            "channel": "com.bink.wallet",
            "auto_link": False,
            "created": True,
            "loyalty_plan_id": cls.scheme_account.id,
        }

        cls.loyalty_card_authorise_headers = {"X-http-path": "loyalty_card_authorise"}
        cls.loyalty_card_add_and_authorise_headers = {"X-http-path": "loyalty_card_authorise"}
        cls.loyalty_card_register_headers = {"X-http-path": "loyalty_card_register"}
        cls.fail_headers = {"X-http-path": "failing_test"}

    @patch('api_messaging.angelia_background.loyalty_card_authorise')
    def loyalty_card_auth_routing(self, mock_loyalty_card_authorise):
        route.route_message(self.loyalty_card_authorise_headers, self.loyalty_card_auth_autolink_created_message)

        self.assertTrue(mock_loyalty_card_authorise.called)

    @patch('api_messaging.angelia_background.loyalty_card_authorise')
    def loyalty_card_add_and_authorise_routing(self, mock_loyalty_card_authorise):
        route.route_message(self.loyalty_card_add_and_authorise_headers,
                            self.loyalty_card_auth_autolink_created_message)

        self.assertTrue(mock_loyalty_card_authorise.called)

    @patch('api_messaging.angelia_background.loyalty_card_register')
    def loyalty_card_register_routing(self, mock_loyalty_card_register):
        route.route_message(self.loyalty_card_register_headers, self.loyalty_card_register_message)

        self.assertTrue(mock_loyalty_card_register.called)

    def test_failed_route(self):
        with self.assertRaises(InvalidMessagePath):
            route.route_message(self.fail_headers, self.loyalty_card_auth_autolink_created_message)

    @patch('api_messaging.angelia_background.async_link')
    def test_loyalty_card_authorise_created(self, mock_async_link):
        """Tests AUTH routing for an existing loyalty card with auto-linking"""
        angelia_background.loyalty_card_authorise(self.loyalty_card_auth_autolink_created_message)

        self.assertTrue(mock_async_link.called)

    @patch('api_messaging.angelia_background.auto_link_membership_to_payments')
    def test_loyalty_card_authorise_existing(self, mock_auto_link_function):
        """Tests AUTH routing for an existing loyalty card with auto-linking"""
        angelia_background.loyalty_card_authorise(self.loyalty_card_auth_autolink_existing_message)

        self.assertTrue(mock_auto_link_function.called)

    @patch('api_messaging.angelia_background.auto_link_membership_to_payments')
    def test_loyalty_card_authorise_no_autolink(self, mock_auto_link_function):
        """Tests AUTH routing for an existing loyalty card without auto-linking """

        angelia_background.loyalty_card_authorise(self.loyalty_card_auth_no_autolink_existing_message)

        self.assertFalse(mock_auto_link_function.called)

    @patch('api_messaging.angelia_background.MembershipCardView._handle_registration_route')
    def test_loyalty_card_register_journey(self, mock_handle_registration):
        """Tests routing for an existing ADD loyalty card without auto-linking. """

        angelia_background.loyalty_card_register(self.loyalty_card_register_message)

        self.assertTrue(mock_handle_registration.called)

    @patch('api_messaging.angelia_background.deleted_membership_card_cleanup')
    def test_delete_loyalty_card_journey(self, mock_deleted_card_cleanup):
        """Tests successful routing for a DELETE loyalty card journey. """

        angelia_background.delete_loyalty_card(self.delete_loyalty_card_message)

        self.assertTrue(mock_deleted_card_cleanup.called)
