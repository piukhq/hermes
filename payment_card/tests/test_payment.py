from unittest.mock import MagicMock, patch

import requests
from django.conf import settings
from django.urls import reverse
from faker import Factory
from shared_config_storage.credentials.encryption import BLAKE2sHash

from hermes.spreedly import Spreedly, SpreedlyError
from hermes.tasks import RetryTaskStore
from history.utils import GlobalMockAPITestCase
from payment_card.models import PaymentAudit, PaymentCardAccount, PaymentStatus
from payment_card.payment import Payment, PaymentError
from payment_card.tests.factories import PaymentAuditFactory, PaymentCardAccountFactory
from scheme.models import SchemeAccount
from scheme.tests.factories import SchemeAccountFactory
from ubiquity.channel_vault import SecretKeyName
from ubiquity.tests.factories import PaymentCardAccountEntryFactory, SchemeAccountEntryFactory
from user.tests.factories import ClientApplicationFactory, OrganisationFactory, UserFactory

TEST_HASH = "testhash"
TEST_SECRET = "secret"
TEST_SPREEDLY_ENVIRONMENT_KEY = "test_env_key"
TEST_SPREEDLY_ACCESS_SECRET = "test_access_secret"

mock_secret_keys = {
    SecretKeyName.PCARD_HASH_SECRET: "secret",
    SecretKeyName.SPREEDLY_ENVIRONMENT_KEY: "test_env_key",
    SecretKeyName.SPREEDLY_ACCESS_SECRET: "test_access_secret",
    SecretKeyName.SPREEDLY_GATEWAY_TOKEN: "test_gateway",
}


class TestPayment(GlobalMockAPITestCase):
    @classmethod
    def setUpTestData(cls):
        fake = Factory.create()
        cls.organisation = OrganisationFactory(name=fake.text(max_nb_chars=100))
        cls.client_app = ClientApplicationFactory(organisation=cls.organisation, name=fake.text(max_nb_chars=100))
        cls.user = UserFactory()
        cls.scheme_account = SchemeAccountFactory()
        test_hash = BLAKE2sHash().new(obj=TEST_HASH, key=TEST_SECRET)
        cls.payment_card_account = PaymentCardAccountFactory(hash=test_hash)
        PaymentCardAccountEntryFactory(user=cls.user, payment_card_account=cls.payment_card_account)

        cls.spreedly = Spreedly(TEST_SPREEDLY_ENVIRONMENT_KEY, TEST_SPREEDLY_ACCESS_SECRET)

    @patch("ubiquity.channel_vault._secret_keys", mock_secret_keys)
    @patch("requests.post", autospec=True)
    def test_purchase_success(self, mock_post):
        response = {"transaction": {"token": "abc-123", "succeeded": True}}
        mock_post.return_value.json.return_value = response
        payment_token = "abc"
        audit = PaymentAuditFactory(scheme_account=self.scheme_account)
        payment = Payment(audit_obj=audit, payment_token=payment_token, amount=100)

        payment._purchase()

        self.assertTrue(mock_post.called)
        self.assertEqual(payment.spreedly.purchase_resp, response)
        self.assertEqual(payment.spreedly.transaction_token, response["transaction"]["token"])

    @patch("ubiquity.channel_vault._secret_keys", mock_secret_keys)
    @patch("requests.post", autospec=True)
    def test_purchase_missing_token_raises_payment_error(self, mock_post):
        audit = PaymentAuditFactory(scheme_account=self.scheme_account)
        payment = Payment(audit_obj=audit, amount=100)

        with self.assertRaises(PaymentError):
            payment._purchase()

        self.assertFalse(mock_post.called)

    @patch("ubiquity.channel_vault._secret_keys", mock_secret_keys)
    @patch("requests.post", autospec=True)
    def test_purchase_request_exception_raises_payment_error(self, mock_post):
        mock_post.side_effect = requests.ConnectionError
        payment_token = "abc"
        audit = PaymentAuditFactory(scheme_account=self.scheme_account)
        payment = Payment(audit_obj=audit, payment_token=payment_token, amount=100)

        with self.assertRaises(PaymentError):
            payment._purchase()

        self.assertTrue(mock_post.called)

    @patch("ubiquity.channel_vault._secret_keys", mock_secret_keys)
    @patch("requests.post", autospec=True)
    def test_purchase_unexpected_response_raises_payment_error(self, mock_post):
        response = {"transaction": {"token": "abc-123", "missing_succeeded_key": True}}
        mock_post.return_value.json.return_value = response
        payment_token = "abc"
        audit = PaymentAuditFactory(scheme_account=self.scheme_account)
        payment = Payment(audit_obj=audit, payment_token=payment_token, amount=100)

        with self.assertRaises(PaymentError):
            payment._purchase()

        self.assertTrue(mock_post.called)
        self.assertEqual(payment.spreedly.purchase_resp, response)
        self.assertNotEqual(payment.spreedly.transaction_token, response["transaction"]["token"])

    @patch("ubiquity.channel_vault._secret_keys", mock_secret_keys)
    @patch("requests.post", autospec=True)
    def test_purchase_unsuccessful_response_raises_payment_error(self, mock_post):
        response = {"transaction": {"token": "abc-123", "succeeded": False, "response": {}}}
        mock_post.return_value.json.return_value = response
        payment_token = "abc"
        audit = PaymentAuditFactory(scheme_account=self.scheme_account)
        payment = Payment(audit_obj=audit, payment_token=payment_token, amount=100)

        with self.assertRaises(PaymentError):
            payment._purchase()

        self.assertTrue(mock_post.called)
        self.assertEqual(payment.spreedly.purchase_resp, response)
        self.assertNotEqual(payment.spreedly.transaction_token, response["transaction"]["token"])

    @patch("ubiquity.channel_vault._secret_keys", mock_secret_keys)
    @patch("requests.post", autospec=True)
    def test_void_success(self, mock_post):
        response = {"transaction": {"succeeded": True}}
        mock_post.return_value.json.return_value = response
        audit = PaymentAuditFactory(scheme_account=self.scheme_account)
        payment_token = "abc"

        payment = Payment(audit_obj=audit, payment_token=payment_token, amount=100)

        payment._void(transaction_token="abc")

        self.assertTrue(mock_post.called)

    @patch("ubiquity.channel_vault._secret_keys", mock_secret_keys)
    @patch("requests.post", autospec=True)
    def test_void_missing_transaction_token_raises_payment_error(self, mock_post):
        response = {"transaction": {"succeeded": True}}
        mock_post.return_value.json.return_value = response
        audit = PaymentAuditFactory(scheme_account=self.scheme_account)
        payment_token = "abc"

        payment = Payment(audit_obj=audit, payment_token=payment_token, amount=100)

        with self.assertRaises(PaymentError):
            payment._void()

        self.assertFalse(mock_post.called)

    @patch("ubiquity.channel_vault._secret_keys", mock_secret_keys)
    @patch("requests.post", autospec=True)
    def test_void_request_exception_raises_payment_error(self, mock_post):
        mock_post.side_effect = requests.RequestException

        audit = PaymentAuditFactory(scheme_account=self.scheme_account)
        payment_token = "abc"

        payment = Payment(audit_obj=audit, payment_token=payment_token, amount=100)

        with self.assertRaises(PaymentError):
            payment._void(transaction_token="abc")

        self.assertTrue(mock_post.called)

    @patch("ubiquity.channel_vault._secret_keys", mock_secret_keys)
    @patch("requests.post", autospec=True)
    def test_void_unexpected_response_raises_payment_error(self, mock_post):
        response = {"transaction": {"missing_succeeded_key": True}}
        mock_post.return_value.json.return_value = response
        audit = PaymentAuditFactory(scheme_account=self.scheme_account)
        payment_token = "abc"

        payment = Payment(audit_obj=audit, payment_token=payment_token, amount=100)

        with self.assertRaises(PaymentError):
            payment._void(transaction_token="abc")

        self.assertTrue(mock_post.called)

    @patch("ubiquity.channel_vault._secret_keys", mock_secret_keys)
    @patch("requests.post", autospec=True)
    def test_void_failure_response_raises_payment_error(self, mock_post):
        response = {"transaction": {"succeeded": False, "response": {}}}
        mock_post.return_value.json.return_value = response
        audit = PaymentAuditFactory(scheme_account=self.scheme_account)
        payment_token = "abc"

        payment = Payment(audit_obj=audit, payment_token=payment_token, amount=100)

        with self.assertRaises(PaymentError):
            payment._void(transaction_token="abc")

        self.assertTrue(mock_post.called)

    @patch("payment_card.payment.get_secret_key", autospec=True)
    @patch("payment_card.payment.Payment", autospec=True)
    def test_process_payment_purchase_success(self, mock_payment_class, mock_get_hash_secret):
        mock_get_hash_secret.return_value = TEST_SECRET
        mock_payment_class.attempt_purchase = Payment.attempt_purchase
        mock_spreedly = MagicMock()
        mock_spreedly.transaction_token = "abc"
        mock_payment_class.return_value.spreedly = mock_spreedly

        audit_obj_count = PaymentAudit.objects.count()
        self.assertEqual(0, audit_obj_count)

        Payment.process_payment_purchase(
            scheme_acc=self.scheme_account, payment_card_hash=TEST_HASH, user_id=self.user.id, payment_amount=200
        )

        audit_obj_count = PaymentAudit.objects.count()
        self.assertEqual(1, audit_obj_count)

        audit_obj = PaymentAudit.objects.get(scheme_account=self.scheme_account)

        self.assertTrue(mock_get_hash_secret.called)
        self.assertTrue(mock_payment_class.called)
        self.assertEqual("abc", audit_obj.transaction_token)
        self.assertEqual(audit_obj.status, PaymentStatus.AUTHORISED)
        self.assertEqual(audit_obj.payment_card_id, self.payment_card_account.id)
        self.assertEqual(audit_obj.payment_card_hash, self.payment_card_account.hash)

    @patch("payment_card.payment.get_secret_key", autospec=True)
    @patch("payment_card.payment.Payment._purchase", autospec=True)
    def test_process_payment_purchase_invalid_p_card_id_raises_payment_error(
        self, mock_purchase_call, mock_get_hash_secret
    ):
        mock_get_hash_secret.return_value = TEST_SECRET
        audit_obj_count = PaymentAudit.objects.count()
        self.assertEqual(0, audit_obj_count)

        invalid_p_card_hash = "badhash"

        with self.assertRaises(PaymentCardAccount.DoesNotExist):
            Payment.process_payment_purchase(
                scheme_acc=self.scheme_account,
                payment_card_hash=invalid_p_card_hash,
                user_id=self.user.id,
                payment_amount=200,
            )

        audit_obj_count = PaymentAudit.objects.count()
        self.assertEqual(1, audit_obj_count)

        audit_obj = PaymentAudit.objects.get(scheme_account=self.scheme_account)

        self.assertTrue(mock_get_hash_secret.called)
        self.assertFalse(mock_purchase_call.return_value._purchase.called)
        self.assertEqual(audit_obj.status, PaymentStatus.PURCHASE_FAILED)

    @patch("payment_card.payment.get_secret_key", autospec=True)
    @patch("payment_card.payment.Payment._purchase", autospec=True)
    def test_process_payment_purchase_p_card_id_not_associated_with_service(
        self, mock_purchase_call, mock_get_hash_secret
    ):
        mock_get_hash_secret.return_value = TEST_SECRET
        audit_obj_count = PaymentAudit.objects.count()
        self.assertEqual(0, audit_obj_count)
        invalid_user = UserFactory()

        with self.assertRaises(PaymentCardAccount.DoesNotExist):
            Payment.process_payment_purchase(
                scheme_acc=self.scheme_account, payment_card_hash=TEST_HASH, user_id=invalid_user.id, payment_amount=200
            )

        audit_obj_count = PaymentAudit.objects.count()
        self.assertEqual(1, audit_obj_count)

        audit_obj = PaymentAudit.objects.get(scheme_account=self.scheme_account)

        self.assertTrue(mock_get_hash_secret.called)
        self.assertFalse(mock_purchase_call.return_value._purchase.called)
        self.assertEqual(audit_obj.status, PaymentStatus.PURCHASE_FAILED)
        self.assertNotEqual(audit_obj.payment_card_id, self.payment_card_account.id)
        self.assertEqual(audit_obj.payment_card_hash, self.payment_card_account.hash)

    @patch("payment_card.payment.get_secret_key", autospec=True)
    @patch("payment_card.payment.Payment._purchase", autospec=True)
    def test_process_payment_purchase_sets_correct_status_for_failures(self, mock_purchase_call, mock_get_hash_secret):
        mock_get_hash_secret.return_value = TEST_SECRET
        mock_purchase_call.side_effect = PaymentError
        audit_obj_count = PaymentAudit.objects.count()
        self.assertEqual(0, audit_obj_count)

        with self.assertRaises(PaymentError):
            Payment.process_payment_purchase(
                scheme_acc=self.scheme_account, payment_card_hash=TEST_HASH, user_id=self.user.id, payment_amount=200
            )

        audit_obj_count = PaymentAudit.objects.count()
        self.assertEqual(1, audit_obj_count)

        audit_obj = PaymentAudit.objects.get(scheme_account=self.scheme_account)

        self.assertTrue(mock_get_hash_secret.called)
        self.assertTrue(mock_purchase_call.called)
        self.assertEqual(audit_obj.status, PaymentStatus.PURCHASE_FAILED)
        self.assertEqual(audit_obj.payment_card_id, self.payment_card_account.id)
        self.assertEqual(audit_obj.payment_card_hash, self.payment_card_account.hash)

    @patch("payment_card.payment.get_secret_key", autospec=True)
    @patch("payment_card.payment.Payment._purchase", autospec=True)
    def test_process_payment_purchase_retries_on_system_failures(self, mock_purchase_call, mock_get_hash_secret):
        mock_get_hash_secret.return_value = TEST_SECRET
        mock_purchase_call.side_effect = PaymentError

        with self.assertRaises(PaymentError):
            Payment.process_payment_purchase(
                scheme_acc=self.scheme_account, payment_card_hash=TEST_HASH, user_id=self.user.id, payment_amount=200
            )

        self.assertTrue(mock_get_hash_secret.called)
        self.assertTrue(mock_purchase_call.called)
        self.assertEqual(mock_purchase_call.call_count, 4)

    @patch("payment_card.payment.get_secret_key", autospec=True)
    @patch("payment_card.payment.Payment._purchase", autospec=True)
    def test_process_payment_purchase_does_not_retry_on_spreedly_error_response(
        self, mock_purchase_call, mock_get_hash_secret
    ):
        mock_get_hash_secret.return_value = TEST_SECRET
        mock_purchase_call.side_effect = PaymentError(SpreedlyError.UNSUCCESSFUL_RESPONSE)

        with self.assertRaises(PaymentError):
            Payment.process_payment_purchase(
                scheme_acc=self.scheme_account, payment_card_hash=TEST_HASH, user_id=self.user.id, payment_amount=200
            )

        self.assertTrue(mock_get_hash_secret.called)
        self.assertTrue(mock_purchase_call.called)
        self.assertEqual(mock_purchase_call.call_count, 1)

    @patch("ubiquity.channel_vault._secret_keys", mock_secret_keys)
    @patch.object(Payment, "_void", autospec=True)
    def test_process_payment_void_success(self, mock_void):
        audit = PaymentAuditFactory(
            scheme_account=self.scheme_account, status=PaymentStatus.AUTHORISED, transaction_token="qwerty"
        )

        Payment.process_payment_void(self.scheme_account)

        audit.refresh_from_db()

        self.assertTrue(mock_void.called)
        self.assertEqual(audit.status, PaymentStatus.VOID_SUCCESSFUL)
        self.assertEqual(audit.void_attempts, 1)
        self.assertEqual(audit.transaction_token, "")

    @patch.object(Payment, "_void", autospec=True)
    def test_process_payment_void_does_not_call_void_without_audit(self, mock_void):
        Payment.process_payment_void(self.scheme_account)
        self.assertFalse(mock_void.called)

    @patch("ubiquity.channel_vault._secret_keys", mock_secret_keys)
    @patch.object(RetryTaskStore, "set_task", autospec=True)
    @patch.object(Payment, "_void", autospec=True)
    def test_process_payment_void_error_sets_retry_task(self, mock_void, mock_set_task):
        mock_void.side_effect = PaymentError
        audit = PaymentAuditFactory(
            scheme_account=self.scheme_account, status=PaymentStatus.AUTHORISED, transaction_token="qwerty"
        )

        Payment.process_payment_void(self.scheme_account)

        audit.refresh_from_db()

        self.assertTrue(mock_void.called)
        self.assertEqual(audit.status, PaymentStatus.VOID_REQUIRED)
        self.assertEqual(audit.void_attempts, 1)
        self.assertNotEqual(audit.transaction_token, "")
        self.assertTrue(mock_set_task.called)
        for arg in ["payment_card.tasks", "retry_payment_void_task", {"scheme_acc_id": self.scheme_account.id}]:
            self.assertIn(arg, list(mock_set_task.call_args_list)[0][0])

    @patch.object(PaymentAudit, "save", autospec=True)
    def test_process_payment_success_does_nothing_if_no_audit(self, mock_save):
        Payment.process_payment_success(scheme_acc=self.scheme_account)
        self.assertFalse(mock_save.called)

    def test_process_payment_success_changes_audit_status(self):
        for status in [PaymentStatus.VOID_REQUIRED, PaymentStatus.AUTHORISED]:
            audit = PaymentAuditFactory(status=status, scheme_account=self.scheme_account)
            Payment.process_payment_success(scheme_acc=self.scheme_account)

            audit.refresh_from_db()
            self.assertEqual(audit.status, PaymentStatus.SUCCESSFUL)

    @patch("ubiquity.channel_vault._secret_keys", mock_secret_keys)
    @patch("payment_card.payment.sentry_sdk.capture_message")
    @patch.object(Payment, "_void", autospec=True)
    def test_payment_audit_signal_raises_sentry_message_after_too_many_retries(self, mock_void, mock_capture_message):
        payment_audit = PaymentAuditFactory(scheme_account=self.scheme_account)
        payment_audit.void_attempts = 9
        mock_void.side_effect = PaymentError

        with self.assertRaises(PaymentError):
            Payment.attempt_void(payment_audit)

        self.assertTrue(mock_void.called)
        self.assertTrue(mock_capture_message.called)
        self.assertEqual(mock_capture_message.call_count, 1)

    @patch("analytics.api.requests.post")
    @patch("scheme.views.async_join_journey_fetch_balance_and_update_status")
    @patch.object(Payment, "process_payment_void")
    @patch.object(Payment, "process_payment_success")
    def test_successful_join_processes_successful_payment(self, mock_payment_success, mock_payment_void, *_):
        scheme_account = SchemeAccountFactory(status=SchemeAccount.JOIN_ASYNC_IN_PROGRESS)
        SchemeAccountEntryFactory(scheme_account=scheme_account, user=self.user)
        user_set = str(self.user.id)

        auth_headers = {"HTTP_AUTHORIZATION": "Token " + settings.SERVICE_API_KEY}
        data = {"status": SchemeAccount.ACTIVE, "journey": "join", "user_info": {"user_set": user_set}}
        response = self.client.post(
            reverse("change_account_status", args=[scheme_account.id]), data, format="json", **auth_headers
        )

        self.assertEqual(response.status_code, 200)
        scheme_account.refresh_from_db()
        self.assertEqual(scheme_account.status, SchemeAccount.ACTIVE)
        self.assertTrue(mock_payment_success.called)
        self.assertFalse(mock_payment_void.called)

    @patch("analytics.api.requests.post")
    @patch("scheme.views.async_join_journey_fetch_balance_and_update_status")
    @patch.object(Payment, "process_payment_void")
    @patch.object(Payment, "process_payment_success")
    def test_failed_join_voids_payment(self, mock_payment_success, mock_payment_void, *_):
        scheme_account = SchemeAccountFactory(status=SchemeAccount.JOIN_ASYNC_IN_PROGRESS)
        SchemeAccountEntryFactory(scheme_account=scheme_account, user=self.user)
        user_set = str(self.user.id)

        auth_headers = {"HTTP_AUTHORIZATION": "Token " + settings.SERVICE_API_KEY}
        data = {"status": SchemeAccount.ENROL_FAILED, "journey": "join", "user_info": {"user_set": user_set}}
        response = self.client.post(
            reverse("change_account_status", args=[scheme_account.id]), data, format="json", **auth_headers
        )

        self.assertEqual(response.status_code, 200)
        scheme_account.refresh_from_db()
        self.assertEqual(scheme_account.status, SchemeAccount.ENROL_FAILED)
        self.assertTrue(mock_payment_void.called)
        self.assertFalse(mock_payment_success.called)
