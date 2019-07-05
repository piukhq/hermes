from unittest.mock import patch, MagicMock

from rest_framework.test import APITestCase

from hermes.tasks import RetryTaskStore
from payment_card.models import PaymentAudit, PaymentStatus
from payment_card.payment import Payment, PaymentError
from payment_card.tests.factories import PaymentCardAccountFactory, PaymentAuditFactory
from scheme.tests.factories import SchemeAccountFactory
from ubiquity.tests.factories import PaymentCardAccountEntryFactory, SchemeAccountEntryFactory
from user.tests.factories import UserFactory


class TestPayment(APITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.scheme_account = SchemeAccountFactory()
        self.payment_card_account = PaymentCardAccountFactory()
        self.p_link = PaymentCardAccountEntryFactory(payment_card_account=self.payment_card_account, user=self.user)
        self.s_link = SchemeAccountEntryFactory(scheme_account=self.scheme_account, user=self.user)

    def test_auth_success(self):
        pass

    def test_auth_missing_token_raises_payment_error(self):
        pass

    def test_auth_request_exception_raises_payment_error(self):
        pass

    def test_void_success(self):
        pass

    def test_void_missing_token_raises_payment_error(self):
        pass

    def test_void_request_exception_raises_payment_error(self):
        pass

    def test_void_unexpected_response_raises_payment_error(self):
        pass

    def test_void_failure_response_raises_payment_error(self):
        pass

    @patch('payment_card.payment.Payment', autospec=True)
    def test_process_payment_auth_success(self, payment_instance):
        mock_payment_instance = MagicMock()
        mock_payment_instance.transaction_id = 'abc'
        payment_instance.return_value = mock_payment_instance

        audit_obj_count = PaymentAudit.objects.count()
        self.assertEqual(0, audit_obj_count)

        Payment.process_payment_auth(
            user_id=self.user.id,
            scheme_acc=self.scheme_account,
            payment_card_id=self.payment_card_account.id,
            payment_amount=200
        )

        audit_obj_count = PaymentAudit.objects.count()
        self.assertEqual(1, audit_obj_count)

        audit_obj = PaymentAudit.objects.get(scheme_account=self.scheme_account, user_id=self.user.id)

        self.assertTrue(payment_instance.return_value.auth.called)
        self.assertEqual(payment_instance.return_value.transaction_id, audit_obj.transaction_id)
        self.assertEqual(audit_obj.status, PaymentStatus.AUTHORISED)

    @patch('payment_card.payment.Payment', autospec=True)
    def test_process_payment_auth_invalid_p_card_id_raises_payment_error(self, payment_instance):
        audit_obj_count = PaymentAudit.objects.count()
        self.assertEqual(0, audit_obj_count)

        invalid_p_card_id = 99999999999999999

        with self.assertRaises(PaymentError):
            Payment.process_payment_auth(
                user_id=self.user.id,
                scheme_acc=self.scheme_account,
                payment_card_id=invalid_p_card_id,
                payment_amount=200
            )

        audit_obj_count = PaymentAudit.objects.count()
        self.assertEqual(1, audit_obj_count)

        audit_obj = PaymentAudit.objects.get(scheme_account=self.scheme_account, user_id=self.user.id)

        self.assertFalse(payment_instance.return_value.auth.called)
        self.assertEqual(audit_obj.status, PaymentStatus.AUTH_FAILED)

    @patch('payment_card.payment.Payment', autospec=True)
    def test_process_payment_auth_sets_correct_status_for_failures(self, payment_instance):
        payment_instance.return_value.auth.side_effect = PaymentError
        audit_obj_count = PaymentAudit.objects.count()
        self.assertEqual(0, audit_obj_count)

        with self.assertRaises(PaymentError):
            Payment.process_payment_auth(
                user_id=self.user.id,
                scheme_acc=self.scheme_account,
                payment_card_id=self.payment_card_account.id,
                payment_amount=200
            )

        audit_obj_count = PaymentAudit.objects.count()
        self.assertEqual(1, audit_obj_count)

        audit_obj = PaymentAudit.objects.get(scheme_account=self.scheme_account, user_id=self.user.id)

        self.assertTrue(payment_instance.return_value.auth.called)
        self.assertEqual(audit_obj.status, PaymentStatus.AUTH_FAILED)

    @patch.object(Payment, 'void', autospec=True)
    def test_process_payment_void_success(self, mock_void):
        audit = PaymentAuditFactory(
            scheme_account=self.scheme_account,
            status=PaymentStatus.AUTHORISED,
            transaction_id='qwerty'
        )

        Payment.process_payment_void(self.scheme_account)

        audit.refresh_from_db()

        self.assertTrue(mock_void.called)
        self.assertEqual(audit.status, PaymentStatus.VOID_SUCCESSFUL)
        self.assertEqual(audit.void_attempts, 1)
        self.assertEqual(audit.transaction_id, None)

    @patch.object(Payment, 'void', autospec=True)
    def test_process_payment_void_does_not_call_void_without_audit(self, mock_void):
        Payment.process_payment_void(self.scheme_account)
        self.assertFalse(mock_void.called)

    @patch.object(RetryTaskStore, 'set_task', autospec=True)
    @patch.object(Payment, 'void', autospec=True)
    def test_process_payment_void_error_sets_retry_task(self, mock_void, mock_set_task):
        mock_void.side_effect = PaymentError
        audit = PaymentAuditFactory(
            scheme_account=self.scheme_account,
            status=PaymentStatus.AUTHORISED,
            transaction_id='qwerty'
        )

        Payment.process_payment_void(self.scheme_account)

        audit.refresh_from_db()

        self.assertTrue(mock_void.called)
        self.assertEqual(audit.status, PaymentStatus.VOID_REQUIRED)
        self.assertEqual(audit.void_attempts, 1)
        self.assertNotEqual(audit.transaction_id, None)
        self.assertTrue(mock_set_task.called)
        for arg in ['payment_card.tasks', 'retry_payment_void_task', {'scheme_acc_id': self.scheme_account.id}]:
            self.assertIn(arg, list(mock_set_task.call_args_list)[0][0])

    @patch.object(PaymentAudit, 'save', autospec=True)
    def test_process_payment_success_returns_none_if_no_audit(self, mock_save):
        Payment.process_payment_success(scheme_acc=self.scheme_account)

        self.assertFalse(mock_save.called)

    def test_process_payment_success_changes_audit_status(self):
        for status in [PaymentStatus.VOID_REQUIRED, PaymentStatus.AUTHORISED]:
            audit = PaymentAuditFactory(status=status, scheme_account=self.scheme_account)
            Payment.process_payment_success(scheme_acc=self.scheme_account)

            audit.refresh_from_db()
            self.assertEqual(audit.status, PaymentStatus.SUCCESS)
