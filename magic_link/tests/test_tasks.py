from unittest.mock import patch

from django.core import mail
from rest_framework.test import APITestCase

from magic_link.tasks import send_magic_link


class TestTask(APITestCase):

    @classmethod
    def setUpTestData(cls):
        cls.test_email = 'test-bink@bink.com'

    @patch('magic_link.tasks.get_email_template', return_value=('', ''))
    @patch('magic_link.tasks.populate_template', return_value='')
    def test_send_magic_link(self, mock_get_email_template, mock_populate_template):
        send_magic_link(
            email=self.test_email,
            email_from='test_from_email@bink.com',
            subject='Some subject',
            slug='wasabi-club',
            token='some_token',
            external_name='web',
            bundle_id='.com.wasabi.bink.web'
        )

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, 'Some subject')
        self.assertEqual(mail.outbox[0].from_email, 'test_from_email@bink.com')
        self.assertEqual(mail.outbox[0].reply_to, ['no-reply@bink.com'])
