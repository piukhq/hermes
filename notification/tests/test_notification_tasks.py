from base64 import b64encode
from datetime import timedelta
from unittest import mock

import pysftp
from django.conf import settings
from django.utils import timezone
from paramiko import SSHException, RSAKey

from history.models import HistoricalSchemeAccount, HistoricalSchemeAccountEntry
from history.utils import GlobalMockAPITestCase
from notification.tasks import SftpManager, NotificationProcessor
from scheme.models import SchemeAccount
from scheme.tests.factories import SchemeAccountFactory
from ubiquity.reason_codes import ubiquity_status_translation
from ubiquity.tests.factories import SchemeAccountEntryFactory
from user.tests.factories import UserFactory, ClientApplicationFactory


class TestNotificationTask(GlobalMockAPITestCase):

    @classmethod
    def setUpTestData(cls):
        cls.test_org = "Barclays"
        cls.barclays_channel = "com.barclays.bmb"
        cls.external_id = "Test_User"
        cls.external_id = "Test_User_Two"
        cls.client_application = ClientApplicationFactory(organisation__name=cls.test_org)
        cls.user = UserFactory(client=cls.client_application, external_id=cls.external_id)
        cls.user_two = UserFactory(client=cls.client_application, external_id=cls.external_id)
        cls.scheme_account = SchemeAccountFactory(status=SchemeAccount.PENDING)
        cls.scheme_account_entry = SchemeAccountEntryFactory(
            user=cls.user, scheme_account=cls.scheme_account
        )

        cls.history_scheme_account = HistoricalSchemeAccount(
            change_type=HistoricalSchemeAccount.CREATE,
            instance_id=cls.scheme_account.id,
            change_details='status',
            body={"id": cls.scheme_account.id, "status": SchemeAccount.PENDING},
            channel=cls.barclays_channel
        ).save()

        settings.NOTIFICATION_ERROR_THRESHOLD = 1
        settings.NOTIFICATION_RETRY_TIMER = 1
        settings.VAULT_CONFIG['LOCAL_SECRETS'] = True

    def test_get_data_initiation(self):
        test_notification = NotificationProcessor()
        data = test_notification.get_data()
        expected_result = (
            self.scheme_account_entry.user.external_id,
            self.scheme_account_entry.scheme_account.scheme.slug,
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
                change_type=HistoricalSchemeAccount.CREATE,
                instance_id=self.scheme_account_entry.scheme_account.id,
                change_details='',
                body={"id": self.scheme_account.id, "status": SchemeAccount.PENDING},
                channel=self.barclays_channel
            ).save()

            HistoricalSchemeAccount(
                change_type=HistoricalSchemeAccount.UPDATE,
                instance_id=self.scheme_account_entry.scheme_account.id,
                change_details='status',
                body={"id": self.scheme_account.id, "status": SchemeAccount.INVALID_CREDENTIALS},
                channel=self.barclays_channel
            ).save()

            HistoricalSchemeAccount(
                change_type=HistoricalSchemeAccount.UPDATE,
                instance_id=self.scheme_account_entry.scheme_account.id,
                change_details='updated',
                body={"id": self.scheme_account.id, "status": SchemeAccount.INVALID_CREDENTIALS},
            ).save()

            HistoricalSchemeAccount(
                change_type=HistoricalSchemeAccount.UPDATE,
                instance_id=self.scheme_account_entry.scheme_account.id,
                change_details='status',
                body={"id": self.scheme_account.id, "status": SchemeAccount.ACTIVE},
            ).save()

            HistoricalSchemeAccount(
                change_type=HistoricalSchemeAccount.DELETE,
                instance_id=self.scheme_account_entry.scheme_account.id,
                change_details='',
                body={"id": self.scheme_account.id, "status": SchemeAccount.INVALID_CREDENTIALS},
                channel=self.barclays_channel
            ).save()

            HistoricalSchemeAccountEntry(
                instance_id=self.scheme_account_entry.id,
                change_type=HistoricalSchemeAccount.DELETE,
                scheme_account_id=self.scheme_account_entry.scheme_account.id,
                user_id=self.user.id,
                channel=self.barclays_channel
            ).save()

        historical_scheme_accounts = HistoricalSchemeAccount.objects.all()
        self.assertEqual(len(historical_scheme_accounts), 6)

        three_hours_plus = timezone.now() + timedelta(hours=3)
        with mock.patch('django.utils.timezone.now', mock.Mock(return_value=three_hours_plus)):
            test_notification = NotificationProcessor(to_date=timezone.now())
            data = test_notification.get_data()

            self.assertEqual(len(data), 4)
            self.assertEqual(data[0][2], 'pending')
            self.assertEqual(data[1][2], SchemeAccount.INVALID_CREDENTIALS)
            self.assertEqual(data[2][2], SchemeAccount.ACTIVE)
            self.assertEqual(data[3][2], 'deleted')

    def test_get_data_with_delete_scheme_account(self):
        settings.NOTIFICATION_RUN = True
        mocked_datetime = timezone.now() + timedelta(hours=2)
        with mock.patch('django.utils.timezone.now', mock.Mock(return_value=mocked_datetime)):
            HistoricalSchemeAccount(
                change_type=HistoricalSchemeAccount.CREATE,
                instance_id=self.scheme_account_entry.scheme_account.id,
                change_details='',
                body={"id": self.scheme_account.id, "status": SchemeAccount.PENDING},
                channel=self.barclays_channel
            ).save()

            self.scheme_account.is_deleted = True
            self.scheme_account.save()

            HistoricalSchemeAccountEntry(
                instance_id=self.scheme_account_entry.id,
                change_type=HistoricalSchemeAccount.DELETE,
                scheme_account_id=self.scheme_account_entry.scheme_account.id,
                user_id=self.user.id,
                channel=self.barclays_channel
            ).save()

            HistoricalSchemeAccount(
                change_type=HistoricalSchemeAccount.DELETE,
                instance_id=self.scheme_account_entry.scheme_account.id,
                change_details='',
                body={"id": self.scheme_account.id, "status": SchemeAccount.ACTIVE},
                channel=self.barclays_channel
            ).save()

        three_hours_plus = timezone.now() + timedelta(hours=3)
        with mock.patch('django.utils.timezone.now', mock.Mock(return_value=three_hours_plus)):
            test_notification = NotificationProcessor(to_date=timezone.now())
            data = test_notification.get_data()

            self.assertEqual(len(data), 2)
            self.assertEqual(data[0][2], 'pending')
            self.assertEqual(data[1][2], 'deleted')

    def test_multi_wallet_get_data(self):
        settings.NOTIFICATION_RUN = True
        mocked_datetime = timezone.now() + timedelta(hours=2)
        with mock.patch('django.utils.timezone.now', mock.Mock(return_value=mocked_datetime)):
            HistoricalSchemeAccount(
                change_type=HistoricalSchemeAccount.CREATE,
                instance_id=self.scheme_account_entry.scheme_account.id,
                change_details='',
                body={"id": self.scheme_account.id, "status": SchemeAccount.PENDING},
                channel=self.barclays_channel
            ).save()

            self.scheme_account.is_deleted = True
            self.scheme_account.save()

            HistoricalSchemeAccountEntry(
                instance_id=self.scheme_account_entry.id,
                change_type=HistoricalSchemeAccount.DELETE,
                scheme_account_id=self.scheme_account_entry.scheme_account.id,
                user_id=self.user.id,
                channel=self.barclays_channel
            ).save()

            HistoricalSchemeAccountEntry(
                instance_id=self.scheme_account_entry.id,
                change_type=HistoricalSchemeAccount.DELETE,
                scheme_account_id=self.scheme_account_entry.scheme_account.id,
                user_id=self.user_two.id,
                channel=self.barclays_channel
            ).save()

            HistoricalSchemeAccount(
                change_type=HistoricalSchemeAccount.DELETE,
                instance_id=self.scheme_account_entry.scheme_account.id,
                change_details='',
                body={"id": self.scheme_account.id, "status": SchemeAccount.ACTIVE},
                channel=self.barclays_channel
            ).save()

        three_hours_plus = timezone.now() + timedelta(hours=3)
        with mock.patch('django.utils.timezone.now', mock.Mock(return_value=three_hours_plus)):
            test_notification = NotificationProcessor(to_date=timezone.now())
            data = test_notification.get_data()

            self.assertEqual(len(data), 4)
            self.assertEqual(data[0][2], 'pending')
            self.assertEqual(data[0][0], self.user.external_id)
            self.assertEqual(data[1][2], 'deleted')
            self.assertEqual(data[1][0], self.user.external_id)
            self.assertEqual(data[2][2], 'pending')
            self.assertEqual(data[2][0], self.user_two.external_id)
            self.assertEqual(data[3][2], 'deleted')
            self.assertEqual(data[3][0], self.user_two.external_id)

    @mock.patch('paramiko.RSAKey.from_private_key')
    def test_data_format(self, mock_rsa_key):
        datetime_now = timezone.now()

        data = [[self.external_id, self.scheme_account.scheme.slug, SchemeAccount.ACTIVE, datetime_now]]
        expected_result = [
            [
                '01',
                self.external_id,
                self.scheme_account.scheme.slug,
                ubiquity_status_translation[SchemeAccount.ACTIVE],
                int(datetime_now.timestamp())
            ]
        ]

        sftp = SftpManager()
        result = sftp.format_data(data)

        self.assertEqual(result, expected_result)

    @mock.patch('paramiko.RSAKey.from_private_key')
    def test_retry_raise_exception(self, mock_rsa_key):
        mock_rsa_key.return_value = RSAKey.generate(1024)
        mock_host_keys = {
            "host": "test.bink.com",
            "key": b64encode("test_host_key".encode('ascii')),
            "keytype": "ssh-ed25519"
        },
        {
            "host": "test.bink.com",
            "key": b64encode("test_host_key".encode('ascii')),
            "keytype": "ssh-rsa"
        }

        sftp = SftpManager(rows=[])
        sftp.sftp_host_keys = mock_host_keys
        with self.assertRaises(SSHException):
            sftp.transfer_file()

    @mock.patch('pysftp.Connection')
    @mock.patch('notification.tasks.SftpManager.transfer_file')
    @mock.patch('paramiko.RSAKey.from_private_key')
    def test_transfer_file(self, mock_connection, mock_transfer, mock_rsa_key):
        # Disable host key checking for tests
        test_cnopts = pysftp.CnOpts()
        test_cnopts.hostkeys = None

        test_data = [
            [self.external_id, self.scheme_account.scheme.slug, SchemeAccount.ACTIVE, timezone.now()]
        ]
        sftp = SftpManager(rows=test_data)
        sftp.cnopts = test_cnopts
        result = sftp.transfer_file()

        self.assertTrue(result)
