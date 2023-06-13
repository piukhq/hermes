from unittest.mock import MagicMock, call, patch

from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import Group
from django.contrib.messages import ERROR, WARNING
from django.test import RequestFactory, TestCase

from payment_card.admin import PaymentCardAccountAdmin
from payment_card.models import PaymentCardAccount
from payment_card.tests.factories import IssuerFactory, PaymentCardAccountFactory, PaymentCardFactory
from periodic_retry.models import PeriodicRetry, PeriodicRetryStatus, RetryTaskList
from user.models import CustomUser


class TestPaymentCardAdmin(TestCase):
    permitted_group_names = ["Scripts Run and Correct", "Scripts Run Only"]

    @classmethod
    def setUpTestData(cls):
        cls.user = CustomUser.objects.create(email="user@bink-test.bink")
        cls.permitted_groups = Group.objects.bulk_create([Group(name=name) for name in cls.permitted_group_names])
        cls.payment_card_account_psd = PaymentCardAccountFactory(
            issuer=IssuerFactory(name="Barclays"),
            payment_card=PaymentCardFactory(slug="visa", system="visa"),
            hash="somehash1",
            status=PaymentCardAccount.PROVIDER_SERVER_DOWN,
        )
        cls.payment_card_account_unknown = PaymentCardAccountFactory(
            issuer=IssuerFactory(name="Barclays"),
            payment_card=PaymentCardFactory(slug="mastercard", system="mastercard"),
            hash="somehash2",
            status=PaymentCardAccount.UNKNOWN,
        )
        cls.payment_card_account_bad_status = PaymentCardAccountFactory(
            issuer=IssuerFactory(name="Barclays"),
            payment_card=PaymentCardFactory(slug="amex", system="amex"),
            hash="somehash3",
            status=PaymentCardAccount.ACTIVE,
        )

    def setUp(self) -> None:
        admin = AdminSite()
        request_factory = RequestFactory()
        self.request = request_factory.post("/admin/payment_card/paymentcardaddcount/")
        self.request.user = self.user
        self.model_admin = PaymentCardAccountAdmin(PaymentCardAccount, admin)

    def test_retry_enrolment_no_permissions(self) -> None:
        qs = PaymentCardAccount.objects.none()
        with patch.object(self.model_admin, "message_user") as mock_message_user:
            self.model_admin.retry_enrolment(self.request, qs)
            mock_message_user.assert_called_once_with(
                self.request,
                f"Only super users and members of the following Groups can use this tool: {self.permitted_group_names}",
                level=ERROR,
            )

    @patch("payment_card.admin.PeriodicRetryHandler")
    def test_retry_enrolment_ok_existing_retry(self, mock_retry_handler_class: MagicMock) -> None:
        mock_retry_handler: MagicMock = mock_retry_handler_class.return_value
        self.user.groups.set(self.permitted_groups)
        PeriodicRetry.objects.create(
            task_group=RetryTaskList.METIS_REQUESTS,
            status=PeriodicRetryStatus.FAILED,
            max_retry_attempts=0,
            data={
                "args": [],
                "kwargs": {},
                "_module": "payment_card.metis",
                "context": {"card_id": self.payment_card_account_psd.id},
                "_function": "retry_enrol",
            },
        )
        self.assertEqual(PeriodicRetry.objects.count(), 1)

        qs = PaymentCardAccount.objects.filter(id=self.payment_card_account_psd.id)
        with patch.object(self.model_admin, "message_user") as mock_message_user:
            self.model_admin.retry_enrolment(self.request, qs)
            mock_message_user.assert_called_once_with(self.request, "Requeued 1 PaymentCardAccount enrolments")

        self.assertEqual(PeriodicRetry.objects.count(), 1)

        retry = PeriodicRetry.objects.get()
        self.assertEqual(retry.max_retry_attempts, 10)
        mock_retry_handler.new.assert_not_called()
        mock_retry_handler.set_task.assert_called_once_with(
            retry, module_name="payment_card.metis", function_name="retry_enrol", data=retry.data
        )

    @patch("periodic_retry.tasks.get_redis_connection")
    def test_retry_enrolment_ok_no_existing_retry(self, mock_get_redis_connection: MagicMock) -> None:
        self.user.groups.set(self.permitted_groups)

        self.assertEqual(PeriodicRetry.objects.count(), 0)

        qs = PaymentCardAccount.objects.filter(id=self.payment_card_account_unknown.id)
        with patch.object(self.model_admin, "message_user") as mock_message_user:
            self.model_admin.retry_enrolment(self.request, qs)
            mock_message_user.assert_called_once_with(self.request, "Requeued 1 PaymentCardAccount enrolments")

        self.assertEqual(PeriodicRetry.objects.count(), 1)

        retry = PeriodicRetry.objects.get()
        self.assertEqual(retry.max_retry_attempts, 10)
        self.assertEqual(retry.data["context"], {"card_id": self.payment_card_account_unknown.id})
        self.assertEqual(retry.results, [{"caused_by": "Manual retry"}])
        self.assertEqual(retry.status, PeriodicRetryStatus.PENDING)

    @patch("payment_card.admin.PeriodicRetryHandler")
    def test_retry_enrolment_multiple_retry_in_non_failed_state(self, mock_retry_handler_class: MagicMock) -> None:
        mock_retry_handler: MagicMock = mock_retry_handler_class.return_value
        self.user.groups.set(self.permitted_groups)
        failed_retry = PeriodicRetry.objects.create(
            task_group=RetryTaskList.METIS_REQUESTS,
            status=PeriodicRetryStatus.FAILED,
            max_retry_attempts=0,
            data={
                "args": [],
                "kwargs": {},
                "_module": "payment_card.metis",
                "context": {"card_id": self.payment_card_account_psd.id},
                "_function": "retry_enrol",
            },
        )
        pending_retry = PeriodicRetry.objects.create(
            task_group=RetryTaskList.METIS_REQUESTS,
            status=PeriodicRetryStatus.PENDING,
            max_retry_attempts=100,
            data={
                "args": [],
                "kwargs": {},
                "_module": "payment_card.metis",
                "context": {"card_id": self.payment_card_account_unknown.id},
                "_function": "retry_enrol",
            },
        )
        self.assertEqual(PeriodicRetry.objects.count(), 2)

        qs = PaymentCardAccount.objects.filter(
            id__in=[self.payment_card_account_psd.id, self.payment_card_account_unknown.id]
        )
        with patch.object(self.model_admin, "message_user") as mock_message_user:
            self.model_admin.retry_enrolment(self.request, qs)
            self.assertEqual(mock_message_user.call_count, 2)
            self.assertEqual(
                mock_message_user.call_args_list[0], call(self.request, "Requeued 1 PaymentCardAccount enrolments")
            )
            self.assertEqual(
                mock_message_user.call_args_list[1],
                call(
                    self.request,
                    "The following PaymentCardAccounts where found to have PeriodicRetrys in non-FAILED state: "
                    f"{[self.payment_card_account_unknown.id]}. Ignoring these.",
                    level=WARNING,
                ),
            )

        self.assertEqual(PeriodicRetry.objects.count(), 2)

        failed_retry.refresh_from_db()
        self.assertEqual(failed_retry.max_retry_attempts, 10)

        pending_retry.refresh_from_db()
        self.assertEqual(pending_retry.max_retry_attempts, 100)

        mock_retry_handler.new.assert_not_called()
        mock_retry_handler.set_task.assert_called_once_with(
            failed_retry, module_name="payment_card.metis", function_name="retry_enrol", data=failed_retry.data
        )

    @patch("payment_card.admin.PeriodicRetryHandler")
    def test_retry_enrolment_multiple_retries_found(self, mock_retry_handler_class: MagicMock) -> None:
        mock_retry_handler: MagicMock = mock_retry_handler_class.return_value
        self.user.groups.set(self.permitted_groups)
        retry_kwargs = {
            "data": {
                "args": [],
                "kwargs": {},
                "_module": "payment_card.metis",
                "context": {"card_id": self.payment_card_account_psd.id},
                "_function": "retry_enrol",
            },
            "task_group": RetryTaskList.METIS_REQUESTS,
            "status": PeriodicRetryStatus.FAILED,
            "max_retry_attempts": 0,
        }

        PeriodicRetry.objects.create(**retry_kwargs)
        PeriodicRetry.objects.create(**retry_kwargs)

        qs = PaymentCardAccount.objects.filter(id=self.payment_card_account_psd.id)
        with patch.object(self.model_admin, "message_user") as mock_message_user:
            self.model_admin.retry_enrolment(self.request, qs)
            mock_message_user.assert_called_once_with(
                self.request,
                "Found multiple PeriodicRetryObjects objecs for PaymentCardAccount with id: "
                f"{self.payment_card_account_psd.id}",
                level=ERROR,
            )
        mock_retry_handler.new.assert_not_called()
        mock_retry_handler.set_task.assert_not_called()
