from unittest.mock import patch

from api_messaging import api2_background, route
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
        cls.add_payment_account_message = {
            "payment_account_id": cls.payment_card_account_entry.payment_card_account.id,
            "user_id": cls.payment_card_account_entry.user.id,
            "channel_id": "com.bink.wallet",
            "auto_link": False,
        }
        cls.add_payment_account_auto_link_message = {
            "payment_account_id": cls.payment_card_account_entry.payment_card_account.id,
            "user_id": cls.payment_card_account_entry.user.id,
            "channel_id": "com.bink.wallet",
            "auto_link": True,
        }
        cls.delete_payment_account_message = {
            "payment_account_id": cls.payment_card_account_entry.payment_card_account.id,
            "user_id": cls.payment_card_account_entry.user.id,
            "channel_id": "com.bink.wallet",
        }
        cls.add_payment_account_headers = {"X-http-path": "add_payment_account"}
        cls.delete_payment_account_headers = {"X-http-path": "delete_payment_account"}
        cls.fail_headers = {"X-http-path": "failing_test"}

    @patch('api_messaging.api2_background.add_payment_account')
    def test_add_routing(self, mock_add_payment_account):
        result = route.route_message(self.add_payment_account_headers, self.add_payment_account_message)

        self.assertTrue(mock_add_payment_account.called)
        self.assertTrue(result)

    @patch('api_messaging.api2_background.delete_payment_account')
    def test_delete_routing(self, mock_delete_payment_account):
        result = route.route_message(self.delete_payment_account_headers, self.delete_payment_account_message)

        self.assertTrue(mock_delete_payment_account.called)
        self.assertTrue(result)

    def test_failed_route(self):
        result = route.route_message(self.fail_headers, self.add_payment_account_message)

        self.assertFalse(result)

    @patch('payment_card.metis.enrol_new_payment_card')
    def test_process_add_payment_card_message(self, mock_metis_enrol):
        api2_background.add_payment_account(self.add_payment_account_message)

        self.assertTrue(mock_metis_enrol.called)

    @patch('payment_card.metis.enrol_new_payment_card')
    def test_process_add_payment_card_message_auto_link(self, mock_metis_enrol):
        api2_background.add_payment_account(self.add_payment_account_auto_link_message)

        self.payment_card_account_entry.refresh_from_db()

        self.assertIsNot(self.payment_card_account_entry.payment_card_account.pll_links, [])
        self.assertTrue(mock_metis_enrol.called)

    def test_process_delete_payment_account_deleted(self):
        objects_pre = PaymentCardAccount.objects.filter(id=self.payment_card_account_entry.id).count()

        api2_background.delete_payment_account(self.delete_payment_account_message)

        objects_post = PaymentCardAccount.objects.filter(id=self.payment_card_account_entry.id).count()

        self.assertEqual(objects_pre, objects_post + 1)
