from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from ubiquity.tests.factories import SchemeAccountEntryFactory


class DataExportTest(TestCase):

    @classmethod
    def setUpClass(cls):
        for _ in range(0, 15):
            SchemeAccountEntryFactory()
        super().setUpClass()

    @patch('user.management.commands.data_export.write_csv')
    def test_command_succeeds(self, mock_write_csv):
        out = StringIO()
        call_command('data_export', stdout=out)
        self.assertIn('data export successful.', out.getvalue())
        self.assertEqual(mock_write_csv.call_count, 2)
