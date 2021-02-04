from io import StringIO
from unittest.mock import patch

from django.core.management import call_command

from history.utils import GlobalMockAPITestCase
from ubiquity.tests.factories import SchemeAccountEntryFactory


class DataExportTest(GlobalMockAPITestCase):

    @classmethod
    def setUpTestData(cls):
        for _ in range(0, 15):
            SchemeAccountEntryFactory()

    @patch('user.management.commands.data_export.write_csv')
    def test_command_succeeds(self, mock_write_csv):
        out = StringIO()
        call_command('data_export', stdout=out)
        self.assertIn('data export successful.', out.getvalue())
        self.assertEqual(mock_write_csv.call_count, 2)
