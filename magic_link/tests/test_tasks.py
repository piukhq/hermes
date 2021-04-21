from datetime import datetime
from time import time
from unittest.mock import patch

from django.core import mail
from django.utils.timezone import make_aware
from rest_framework.test import APITestCase

from magic_link.tasks import send_magic_link


class TestTask(APITestCase):

    @classmethod
    def setUpTestData(cls):
        cls.test_email = 'test-bink@bink.com'

    @patch('magic_link.tasks.get_email_template')
    @patch('magic_link.tasks.send_magic_link')
    def test_send_magic_link(self, mock_template, mock_email):
        expiry_date = make_aware(datetime.fromtimestamp(int(time() + 60)))
        send_magic_link(
            email=self.test_email,
            email_from='test_from_email@bink.com',
            subject='Some subject',
            token='some_token',
            url='test_bink.com',
            external_name='web',
            expiry_date=expiry_date,
        )

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, 'Some subject')
        self.assertEqual(mail.outbox[0].from_email, 'test_from_email@bink.com')
        self.assertEqual(mail.outbox[0].reply_to, ['no-reply@bink.com'])
