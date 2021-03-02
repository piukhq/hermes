from unittest.mock import patch

from django.core import mail
from rest_framework.test import APITestCase

from magic_link.tasks import send_magic_link


class TestTask(APITestCase):

    @classmethod
    def setUpTestData(cls):
        cls.test_email = 'test-bink@bink.com'

    @patch('magic_link.tasks.get_email_template')
    @patch('magic_link.tasks.send_magic_link')
    def test_send_magic_link(self, mock_template, mock_email):
        send_magic_link(
            self.test_email,
            'Expiry',
            'some_token',
            'test_bink.com',
            'web'
        )

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, 'Magic Link Request')
