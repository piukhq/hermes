from django.test import TestCase

from history import tasks
from history.models import HistoricalBase, HistoricalPaymentCardAccount
from payment_card.tests.factories import PaymentCardAccountFactory


class TestTasks(TestCase):

    def setUp(self):
        self.payment_card_account = PaymentCardAccountFactory()

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

        self.assertEqual(len(payment_card_account_history), 1)
        self.assertEqual(
            payment_card_account_history[0].instance_id,
            str(self.payment_card_account.id)
        )
        self.assertEqual(
            payment_card_account_history[0].change_type,
            HistoricalBase.CREATE,
        )
