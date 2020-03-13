from unittest.mock import patch, MagicMock

import requests
from faker import Factory
from rest_framework.test import APITestCase

from hermes.spreedly import SpreedlyError
from hermes.tasks import RetryTaskStore
from payment_card.models import PaymentAudit, PaymentStatus
from payment_card.payment import Payment, PaymentError
from payment_card.tests.factories import PaymentCardAccountFactory, PaymentAuditFactory
from scheme.tests.factories import SchemeAccountFactory
from user.tests.factories import UserFactory, ClientApplicationFactory, OrganisationFactory


class TestPayment(APITestCase):
    def setUp(self):
        fake = Factory.create()
        self.organisation = OrganisationFactory(name=fake.text(max_nb_chars=100))
        self.client = ClientApplicationFactory(organisation=self.organisation, name=fake.text(max_nb_chars=100))
        self.user = UserFactory()
        self.scheme_account = SchemeAccountFactory()
        self.payment_card_account = PaymentCardAccountFactory()

    @patch('requests.post', autospec=True)
    def test_purchase_success(self, mock_post):
        response = {
            "transaction": {
                "token": "abc-123",
                "succeeded": True
            }
        }
        mock_post.return_value.json.return_value = response
        payment_token = 'abc'
        audit = PaymentAuditFactory(scheme_account=self.scheme_account)
        payment = Payment(audit_obj=audit, payment_token=payment_token, amount=100)

        payment._purchase()

        self.assertTrue(mock_post.called)
        self.assertEqual(payment.spreedly.purchase_resp, response)
        self.assertEqual(payment.spreedly.transaction_token, response['transaction']['token'])

    @patch('requests.post', autospec=True)
    def test_purchase_missing_token_raises_payment_error(self, mock_post):
        audit = PaymentAuditFactory(scheme_account=self.scheme_account)
        payment = Payment(audit_obj=audit, amount=100)

        with self.assertRaises(PaymentError):
            payment._purchase()

        self.assertFalse(mock_post.called)

    @patch('requests.post', autospec=True)
    def test_purchase_request_exception_raises_payment_error(self, mock_post):
        mock_post.side_effect = requests.ConnectionError
        payment_token = 'abc'
        audit = PaymentAuditFactory(scheme_account=self.scheme_account)
        payment = Payment(audit_obj=audit, payment_token=payment_token, amount=100)

        with self.assertRaises(PaymentError):
            payment._purchase()

        self.assertTrue(mock_post.called)

    @patch('requests.post', autospec=True)
    def test_purchase_unexpected_response_raises_payment_error(self, mock_post):
        response = {
            "transaction": {
                "token": "abc-123",
                "missing_succeeded_key": True
            }
        }
        mock_post.return_value.json.return_value = response
        payment_token = 'abc'
        audit = PaymentAuditFactory(scheme_account=self.scheme_account)
        payment = Payment(audit_obj=audit, payment_token=payment_token, amount=100)

        with self.assertRaises(PaymentError):
            payment._purchase()

        self.assertTrue(mock_post.called)
        self.assertEqual(payment.spreedly.purchase_resp, response)
        self.assertNotEqual(payment.spreedly.transaction_token, response['transaction']['token'])

    @patch('requests.post', autospec=True)
    def test_purchase_unsuccessful_response_raises_payment_error(self, mock_post):
        response = {
            "transaction": {
                "token": "abc-123",
                "succeeded": False,
                "response": {}
            }
        }
        mock_post.return_value.json.return_value = response
        payment_token = 'abc'
        audit = PaymentAuditFactory(scheme_account=self.scheme_account)
        payment = Payment(audit_obj=audit, payment_token=payment_token, amount=100)

        with self.assertRaises(PaymentError):
            payment._purchase()

        self.assertTrue(mock_post.called)
        self.assertEqual(payment.spreedly.purchase_resp, response)
        self.assertNotEqual(payment.spreedly.transaction_token, response['transaction']['token'])

    @patch('requests.post', autospec=True)
    def test_void_success(self, mock_post):
        response = {
            "transaction": {
                "succeeded": True
            }
        }
        mock_post.return_value.json.return_value = response
        audit = PaymentAuditFactory(scheme_account=self.scheme_account)
        payment_token = 'abc'

        payment = Payment(audit_obj=audit, payment_token=payment_token, amount=100)

        payment._void(transaction_token='abc')

        self.assertTrue(mock_post.called)

    @patch('requests.post', autospec=True)
    def test_void_missing_transaction_token_raises_payment_error(self, mock_post):
        response = {
            "transaction": {
                "succeeded": True
            }
        }
        mock_post.return_value.json.return_value = response
        audit = PaymentAuditFactory(scheme_account=self.scheme_account)
        payment_token = 'abc'

        payment = Payment(audit_obj=audit, payment_token=payment_token, amount=100)

        with self.assertRaises(PaymentError):
            payment._void()

        self.assertFalse(mock_post.called)

    @patch('requests.post', autospec=True)
    def test_void_request_exception_raises_payment_error(self, mock_post):
        mock_post.side_effect = requests.RequestException

        audit = PaymentAuditFactory(scheme_account=self.scheme_account)
        payment_token = 'abc'

        payment = Payment(audit_obj=audit, payment_token=payment_token, amount=100)

        with self.assertRaises(PaymentError):
            payment._void(transaction_token='abc')

        self.assertTrue(mock_post.called)

    @patch('requests.post', autospec=True)
    def test_void_unexpected_response_raises_payment_error(self, mock_post):
        response = {
            "transaction": {
                "missing_succeeded_key": True
            }
        }
        mock_post.return_value.json.return_value = response
        audit = PaymentAuditFactory(scheme_account=self.scheme_account)
        payment_token = 'abc'

        payment = Payment(audit_obj=audit, payment_token=payment_token, amount=100)

        with self.assertRaises(PaymentError):
            payment._void(transaction_token='abc')

        self.assertTrue(mock_post.called)

    @patch('requests.post', autospec=True)
    def test_void_failure_response_raises_payment_error(self, mock_post):
        response = {
            "transaction": {
                "succeeded": False,
                "response": {}
            }
        }
        mock_post.return_value.json.return_value = response
        audit = PaymentAuditFactory(scheme_account=self.scheme_account)
        payment_token = 'abc'

        payment = Payment(audit_obj=audit, payment_token=payment_token, amount=100)

        with self.assertRaises(PaymentError):
            payment._void(transaction_token='abc')

        self.assertTrue(mock_post.called)

    @patch('payment_card.payment.Payment', autospec=True)
    def test_process_payment_purchase_success(self, mock_payment_class):
        mock_payment_class.attempt_purchase = Payment.attempt_purchase
        mock_spreedly = MagicMock()
        mock_spreedly.transaction_token = 'abc'
        mock_payment_class.return_value.spreedly = mock_spreedly

        audit_obj_count = PaymentAudit.objects.count()
        self.assertEqual(0, audit_obj_count)

        Payment.process_payment_purchase(
            scheme_acc=self.scheme_account,
            payment_card_id=self.payment_card_account.id,
            user_id=self.user.id,
            payment_amount=200
        )

        audit_obj_count = PaymentAudit.objects.count()
        self.assertEqual(1, audit_obj_count)

        audit_obj = PaymentAudit.objects.get(scheme_account=self.scheme_account)

        self.assertTrue(mock_payment_class.called)
        self.assertEqual('abc', audit_obj.transaction_token)
        self.assertEqual(audit_obj.status, PaymentStatus.AUTHORISED)

    @patch('payment_card.payment.Payment._purchase', autospec=True)
    def test_process_payment_purchase_invalid_p_card_id_raises_payment_error(self, mock_purchase_call):
        audit_obj_count = PaymentAudit.objects.count()
        self.assertEqual(0, audit_obj_count)

        invalid_p_card_id = 99999999999999999

        with self.assertRaises(PaymentError):
            Payment.process_payment_purchase(
                scheme_acc=self.scheme_account,
                payment_card_id=invalid_p_card_id,
                user_id=self.user.id,
                payment_amount=200
            )

        audit_obj_count = PaymentAudit.objects.count()
        self.assertEqual(1, audit_obj_count)

        audit_obj = PaymentAudit.objects.get(scheme_account=self.scheme_account)

        self.assertFalse(mock_purchase_call.return_value._purchase.called)
        self.assertEqual(audit_obj.status, PaymentStatus.PURCHASE_FAILED)

    @patch('payment_card.payment.Payment._purchase', autospec=True)
    def test_process_payment_purchase_sets_correct_status_for_failures(self, mock_purchase_call):
        mock_purchase_call.side_effect = PaymentError
        audit_obj_count = PaymentAudit.objects.count()
        self.assertEqual(0, audit_obj_count)

        with self.assertRaises(PaymentError):
            Payment.process_payment_purchase(
                scheme_acc=self.scheme_account,
                payment_card_id=self.payment_card_account.id,
                user_id=self.user.id,
                payment_amount=200
            )

        audit_obj_count = PaymentAudit.objects.count()
        self.assertEqual(1, audit_obj_count)

        audit_obj = PaymentAudit.objects.get(scheme_account=self.scheme_account)

        self.assertTrue(mock_purchase_call.called)
        self.assertEqual(audit_obj.status, PaymentStatus.PURCHASE_FAILED)

    @patch('payment_card.payment.Payment._purchase', autospec=True)
    def test_process_payment_purchase_retries_on_system_failures(self, mock_purchase_call):
        mock_purchase_call.side_effect = PaymentError

        with self.assertRaises(PaymentError):
            Payment.process_payment_purchase(
                scheme_acc=self.scheme_account,
                payment_card_id=self.payment_card_account.id,
                user_id=self.user.id,
                payment_amount=200
            )

        self.assertTrue(mock_purchase_call.called)
        self.assertEqual(mock_purchase_call.call_count, 4)

    @patch('payment_card.payment.Payment._purchase', autospec=True)
    def test_process_payment_purchase_does_not_retry_on_spreedly_error_response(self, mock_purchase_call):
        mock_purchase_call.side_effect = PaymentError(SpreedlyError.UNSUCCESSFUL_RESPONSE)

        with self.assertRaises(PaymentError):
            Payment.process_payment_purchase(
                scheme_acc=self.scheme_account,
                payment_card_id=self.payment_card_account.id,
                user_id=self.user.id,
                payment_amount=200
            )

        self.assertTrue(mock_purchase_call.called)
        self.assertEqual(mock_purchase_call.call_count, 1)

    @patch.object(Payment, '_void', autospec=True)
    def test_process_payment_void_success(self, mock_void):
        audit = PaymentAuditFactory(
            scheme_account=self.scheme_account,
            status=PaymentStatus.AUTHORISED,
            transaction_token='qwerty'
        )

        Payment.process_payment_void(self.scheme_account)

        audit.refresh_from_db()

        self.assertTrue(mock_void.called)
        self.assertEqual(audit.status, PaymentStatus.VOID_SUCCESSFUL)
        self.assertEqual(audit.void_attempts, 1)
        self.assertEqual(audit.transaction_token, '')

    @patch.object(Payment, '_void', autospec=True)
    def test_process_payment_void_does_not_call_void_without_audit(self, mock_void):
        Payment.process_payment_void(self.scheme_account)
        self.assertFalse(mock_void.called)

    @patch.object(RetryTaskStore, 'set_task', autospec=True)
    @patch.object(Payment, '_void', autospec=True)
    def test_process_payment_void_error_sets_retry_task(self, mock_void, mock_set_task):
        mock_void.side_effect = PaymentError
        audit = PaymentAuditFactory(
            scheme_account=self.scheme_account,
            status=PaymentStatus.AUTHORISED,
            transaction_token='qwerty'
        )

        Payment.process_payment_void(self.scheme_account)

        audit.refresh_from_db()

        self.assertTrue(mock_void.called)
        self.assertEqual(audit.status, PaymentStatus.VOID_REQUIRED)
        self.assertEqual(audit.void_attempts, 1)
        self.assertNotEqual(audit.transaction_token, '')
        self.assertTrue(mock_set_task.called)
        for arg in ['payment_card.tasks', 'retry_payment_void_task', {'scheme_acc_id': self.scheme_account.id}]:
            self.assertIn(arg, list(mock_set_task.call_args_list)[0][0])

    @patch.object(PaymentAudit, 'save', autospec=True)
    def test_process_payment_success_does_nothing_if_no_audit(self, mock_save):
        Payment.process_payment_success(scheme_acc=self.scheme_account)
        self.assertFalse(mock_save.called)

    def test_process_payment_success_changes_audit_status(self):
        for status in [PaymentStatus.VOID_REQUIRED, PaymentStatus.AUTHORISED]:
            audit = PaymentAuditFactory(status=status, scheme_account=self.scheme_account)
            Payment.process_payment_success(scheme_acc=self.scheme_account)

            audit.refresh_from_db()
            self.assertEqual(audit.status, PaymentStatus.SUCCESSFUL)

    @patch('payment_card.payment.sentry_sdk.capture_message')
    @patch.object(Payment, '_void', autospec=True)
    def test_payment_audit_signal_raises_sentry_message_after_too_many_retries(self, mock_void, mock_capture_message):
        payment_audit = PaymentAuditFactory(scheme_account=self.scheme_account)
        payment_audit.void_attempts = 9
        mock_void.side_effect = PaymentError

        with self.assertRaises(PaymentError):
            Payment.attempt_void(payment_audit)

        self.assertTrue(mock_void.called)
        self.assertTrue(mock_capture_message.called)
        self.assertEqual(mock_capture_message.call_count, 1)
