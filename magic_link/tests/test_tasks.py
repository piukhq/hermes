import datetime
from unittest.mock import patch

from django.core import mail
from rest_framework.test import APITestCase

from magic_link.tasks import send_magic_link
from user.utils import MagicLinkData


class TestTask(APITestCase):

    @classmethod
    def setUpTestData(cls):
        cls.test_email = 'test-bink@bink.com'

    @patch('magic_link.tasks.populate_template', return_value='')
    def test_send_magic_link(self, mock_populate_template):
        magic_link_data = MagicLinkData(
            bundle_id="com.wasabi.bink.com",
            slug="wasabi-club",
            external_name="web",
            email=self.test_email,
            email_from="test_from_email@bink.com",
            subject="Some subject",
            template="Some template",
            url="magic/link/url",
            token="Some token",
            expiry_date=datetime.datetime.now(),
            locale="en_GB"
        )
        send_magic_link(magic_link_data)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, 'Some subject')
        self.assertEqual(mail.outbox[0].from_email, 'test_from_email@bink.com')
        self.assertEqual(mail.outbox[0].reply_to, ['no-reply@bink.com'])
