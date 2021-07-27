from datetime import timedelta
from unittest import mock

import pysftp
from django.conf import settings
from django.utils import timezone
from paramiko import SSHException

from history.models import HistoricalSchemeAccount
from history.utils import GlobalMockAPITestCase
from notification.tasks import SftpManager, NotificationProcessor, STATUS_MAP
from scheme.models import SchemeAccount
from scheme.tests.factories import SchemeAccountFactory
from ubiquity.tests.factories import SchemeAccountEntryFactory
from user.tests.factories import UserFactory, ClientApplicationFactory


class TestNotificationTask(GlobalMockAPITestCase):

    @classmethod
    def setUpTestData(cls):
        cls.test_org = "Barclays"
        cls.external_id = "Test_User"
        cls.client_application = ClientApplicationFactory(organisation__name=cls.test_org)
        cls.user = UserFactory(client=cls.client_application, external_id=cls.external_id)
        cls.scheme_account = SchemeAccountFactory(status=SchemeAccount.PENDING)
        cls.scheme_account_entry = SchemeAccountEntryFactory(
            user=cls.user, scheme_account=cls.scheme_account
        )

        cls.history_scheme_account = HistoricalSchemeAccount(
            change_type=HistoricalSchemeAccount.CREATE,
            instance_id=cls.scheme_account.id,
            change_details='status',
            body={"id": cls.scheme_account.id}
        ).save()

        settings.NOTIFICATION_ERROR_THRESHOLD = 1
        settings.NOTIFICATION_RETRY_TIMER = 1

    def test_get_data_initiation(self):
        test_notification = NotificationProcessor(organisation=self.test_org)
        data = test_notification.get_data()
        expected_result = (
            self.scheme_account_entry.user.external_id,
            self.scheme_account_entry.scheme_account.scheme.name,
            self.scheme_account_entry.scheme_account.status,
            self.scheme_account_entry.scheme_account.created
        )

        self.assertEqual(len(data), 1)
        self.assertEqual(data[0][0], self.scheme_account_entry.user.external_id)
        self.assertEqual(data[0], expected_result)

    def test_get_historical_data(self):
        settings.NOTIFICATION_RUN = True
        mocked_datetime = timezone.now() + timedelta(hours=2)
        with mock.patch('django.utils.timezone.now', mock.Mock(return_value=mocked_datetime)):
            HistoricalSchemeAccount(
                change_type=HistoricalSchemeAccount.UPDATE,
                instance_id=self.scheme_account_entry.scheme_account.id,
                change_details='status',
                body={"id": self.scheme_account.id, "status": SchemeAccount.ACTIVE}
            ).save()

        historical_scheme_accounts = HistoricalSchemeAccount.objects.all()
        self.assertEqual(len(historical_scheme_accounts), 2)
        self.assertEqual(historical_scheme_accounts[1].created, mocked_datetime)

        three_hours_plus = timezone.now() + timedelta(hours=3)
        with mock.patch('django.utils.timezone.now', mock.Mock(return_value=three_hours_plus)):
            test_notification = NotificationProcessor(
                organisation=self.test_org, to_date=timezone.now()
            )
            data = test_notification.get_data()

            self.assertEqual(len(data), 1)
            self.assertEqual(data[0][2], SchemeAccount.ACTIVE)

    def test_data_format(self):
        datetime_now = timezone.now()

        data = [[self.external_id, self.scheme_account.scheme.name, SchemeAccount.ACTIVE, datetime_now]]
        expected_result = [
            [
                '01',
                self.external_id,
                self.scheme_account.scheme.name,
                STATUS_MAP[SchemeAccount.ACTIVE],
                datetime_now.timestamp()
            ]
        ]

        sftp = SftpManager()
        result = sftp.format_data(data)

        self.assertEqual(result, expected_result)

    def test_retry_raise_exception(self):
        sftp = SftpManager(rows=[])
        with self.assertRaises(SSHException):
            sftp.transfer_file()

    @mock.patch('pysftp.Connection')
    @mock.patch('notification.tasks.SftpManager.transfer_file')
    def test_transfer_file(self, mock_connection, mock_transfer):
        # Disable host key checking for tests
        test_cnopts = pysftp.CnOpts()
        test_cnopts.hostkeys = None

        test_data = [
            [self.external_id, self.scheme_account.scheme.name, SchemeAccount.ACTIVE, timezone.now()]
        ]
        sftp = SftpManager(rows=test_data)
        sftp.cnopts = test_cnopts
        result = sftp.transfer_file()

        self.assertTrue(result)
