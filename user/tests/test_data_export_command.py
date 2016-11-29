from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from scheme.tests.factories import SchemeAccountFactory


class DataExportTest(TestCase):

    @classmethod
    def setUpClass(cls):
        for i in range(0, 15):
            SchemeAccountFactory()
        super().setUpClass()

    @patch('user.management.commands.data_export.write_csv')
    def test_command_succeeds(self, mock_write_csv):
        out = StringIO()
        call_command('data_export', stdout=out)
        self.assertIn('data export successful.', out.getvalue())
        self.assertEqual(mock_write_csv.call_count, 2)
