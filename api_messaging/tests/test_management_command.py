from io import StringIO
from unittest.mock import patch

from django.core.management import call_command

from history.utils import GlobalMockAPITestCase


class RunReceiveTest(GlobalMockAPITestCase):
    @patch("api_messaging.management.commands.run_message_receiver.run_receiver")
    def test_run_receiver(self, mock_receiver):
        out = StringIO()
        call_command('run_message_receiver', stdout=out)
        self.assertIn("Running receiver service.", out.getvalue())
        self.assertTrue(mock_receiver.called)
