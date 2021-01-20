from unittest.mock import patch

from django.db.models import signals as db_signals
from django.test import override_settings
from rest_framework.test import APITestCase

from history import signals
from history.models import HistoricalBase
from payment_card.models import PaymentCardAccount
from payment_card.tests.factories import PaymentCardAccountFactory


class TestSignals(APITestCase):

    @classmethod
    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
                       CELERY_TASK_ALWAYS_EAGER=True,
                       BROKER_BACKEND='memory')
    def setUpTestData(cls):
        cls.payment_card_account = PaymentCardAccountFactory(is_deleted=True)

    def test_get_change_type_delete(self):
        change_type, change_details = signals._get_change_type_and_details(
            self.payment_card_account,
            {"signal": db_signals.pre_delete}
        )
        self.assertEqual(change_type, HistoricalBase.DELETE)

        change_type, change_details = signals._get_change_type_and_details(
            self.payment_card_account,
            {"update_fields": ['is_deleted']}
        )
        self.assertEqual(change_type, HistoricalBase.DELETE)

    def test_get_change_type_create(self):
        change_type, change_details = signals._get_change_type_and_details(
            self.payment_card_account,
            {"created": "created"}
        )
        self.assertEqual(change_type, HistoricalBase.CREATE)

    def test_get_change_type_update(self):
        change_type, change_details = signals._get_change_type_and_details(
            self.payment_card_account,
            {"update_fields": ['update']}
        )
        self.assertEqual(change_type, HistoricalBase.UPDATE)

    def test_signal_record_history(self):
        with patch('history.tasks.record_history.delay') as mock_task:
            signals.signal_record_history(
                PaymentCardAccount,
                instance=self.payment_card_account,
                **{"update_fields": ['expiry_year'], "body": {'expiry_year': 2022}}
            )

            self.assertTrue(mock_task.called)