from rest_framework.test import APITestCase

from django.test import override_settings

from history import tasks
from history.models import HistoricalBase, HistoricalPaymentCardAccount
from payment_card.tests.factories import PaymentCardAccountFactory


class TestTasks(APITestCase):

    @classmethod
    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
                       CELERY_TASK_ALWAYS_EAGER=True,
                       BROKER_BACKEND='memory')
    def setUpTestData(cls):
        cls.payment_card_account = PaymentCardAccountFactory()

    def test_record_history(self):
        tasks.record_history(
            "PaymentCardAccount",
            **{
                "body": "some_stuff",
                "instance_id": self.payment_card_account.id,
                "change_type": HistoricalBase.CREATE,
                "channel": "bink"
            }
        )
        payment_card_account_history = HistoricalPaymentCardAccount.objects.all()

        self.assertEqual(len(payment_card_account_history), 2)
        self.assertEqual(
            payment_card_account_history[0].instance_id,
            str(self.payment_card_account.id)
        )
        self.assertEqual(
            payment_card_account_history[0].change_type,
            HistoricalBase.CREATE,
        )
