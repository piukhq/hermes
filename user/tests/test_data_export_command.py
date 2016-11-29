from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from scheme.tests.factories import SchemeAccountFactory


class DataExportTest(TestCase):
    @classmethod
    def setUpClass(cls):
        for i in range(0, 15):
            SchemeAccountFactory()
        super().setUpClass()

    def test_command_succeeds(self):
        out = StringIO()
        call_command('data_export', stdout=out)
        self.assertIn('data export successful.', out.getvalue())
