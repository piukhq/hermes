from unittest.mock import patch

from api_messaging import angelia_background, route
from api_messaging.exceptions import InvalidMessagePath
from history.utils import GlobalMockAPITestCase
from payment_card.models import PaymentCardAccount
from scheme.tests.factories import SchemeAccountFactory
from ubiquity.tests.factories import PaymentCardAccountEntryFactory


class TestMessaging(GlobalMockAPITestCase):

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
