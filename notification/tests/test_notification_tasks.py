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
from ubiquity.reason_codes import ubiquity_status_translation, PENDING, AUTHORISED, DELETED, FAILED, UNAUTHORISED
from ubiquity.tests.factories import SchemeAccountEntryFactory
from user.tests.factories import UserFactory, ClientApplicationFactory


class TestNotificationTask(GlobalMockAPITestCase):

    @classmethod
    def setUpTestData(cls):
        cls.test_org = "Barclays"
        cls.barclays_channel = "com.barclays.bmb"
        cls.external_id = "Test_User"
        cls.external_id_two = "Test_User_Two"
        cls.client_application = ClientApplicationFactory(organisation__name=cls.test_org)
        cls.user = UserFactory(client=cls.client_application, external_id=cls.external_id)
        cls.user_two = UserFactory(client=cls.client_application, external_id=cls.external_id_two)
        cls.scheme_account = SchemeAccountFactory(status=SchemeAccount.PENDING)
        cls.scheme_account_entry = SchemeAccountEntryFactory(
            user=cls.user, scheme_account=cls.scheme_account
        )
        cls.scheme_account_entry_two = SchemeAccountEntryFactory(
            user=cls.user_two, scheme_account=cls.scheme_account
        )

        cls.mocked_datetime = timezone.now() + timedelta(hours=2)

        settings.NOTIFICATION_ERROR_THRESHOLD = 1
        settings.NOTIFICATION_RETRY_TIMER = 1
        settings.VAULT_CONFIG['LOCAL_SECRETS'] = True
        settings.NOTIFICATION_RUN = True

    def test_get_data_initiation(self):
        test_notification = NotificationProcessor()
        data = test_notification.get_data()
        expected_result = [
            (
                self.scheme_account_entry.user.external_id,
                self.scheme_account_entry.scheme_account.scheme.slug,
                self.scheme_account_entry.scheme_account.status,
                self.scheme_account_entry.scheme_account.created
            ),
            (
                self.scheme_account_entry_two.user.external_id,
                self.scheme_account_entry_two.scheme_account.scheme.slug,
                self.scheme_account_entry_two.scheme_account.status,
                self.scheme_account_entry_two.scheme_account.created
            )
        ]

        self.assertEqual(len(data), 2)
        self.assertEqual(data[0][0], self.scheme_account_entry.user.external_id)
        self.assertEqual(data[1][0], self.scheme_account_entry_two.user.external_id)
        self.assertEqual(data[0], expected_result[0])
        self.assertEqual(data[1], expected_result[1])

    def test_get_status_translation(self):
        balance = [{"value": 1480.0}]

        sys_action_required_scheme_account = SchemeAccountFactory(
            status=SchemeAccount.END_SITE_DOWN,
            balances=balance
        )

        notification_processor = NotificationProcessor()
        state = notification_processor.get_status_translation(
            sys_action_required_scheme_account,
            sys_action_required_scheme_account.status
        )

        self.assertEqual(state, AUTHORISED)

        sys_action_required_scheme_account.balances = {}
        sys_action_required_scheme_account.save(update_fields=['balances'])

        state = notification_processor.get_status_translation(
            sys_action_required_scheme_account,
            sys_action_required_scheme_account.status
        )

        self.assertEqual(state, PENDING)

        # Test deleted status
        state = notification_processor.get_status_translation(
            sys_action_required_scheme_account,
            DELETED
        )

        self.assertEqual(state, DELETED)

        sys_action_required_scheme_account.status = SchemeAccount.VALIDATION_ERROR
        sys_action_required_scheme_account.save(update_fields=['status'])

        state = notification_processor.get_status_translation(
            sys_action_required_scheme_account,
            sys_action_required_scheme_account.status
        )

        self.assertEqual(state, FAILED)

        sys_action_required_scheme_account.status = SchemeAccount.INVALID_MFA
        sys_action_required_scheme_account.save(update_fields=['status'])

        state = notification_processor.get_status_translation(
            sys_action_required_scheme_account,
            sys_action_required_scheme_account.status
        )

        self.assertEqual(state, UNAUTHORISED)

    def test_get_scheme_account_history(self):
        scheme_account = SchemeAccountFactory(status=SchemeAccount.PENDING)
        scheme_account_entry = SchemeAccountEntryFactory(user=self.user_two, scheme_account=scheme_account)

        HistoricalSchemeAccountEntry(
            instance_id=scheme_account_entry.id,
            change_type=HistoricalSchemeAccount.CREATE,
            scheme_account_id=scheme_account.id,
            user_id=scheme_account_entry.user.id,
            channel=self.barclays_channel
        ).save()

        HistoricalSchemeAccount(
            change_type=HistoricalSchemeAccount.CREATE,
            instance_id=scheme_account.id,
            change_details='',
            body={"id": scheme_account.id, "status": SchemeAccount.PENDING},
            channel=self.barclays_channel
        ).save()

        with mock.patch('django.utils.timezone.now', mock.Mock(return_value=self.mocked_datetime)):
            scheme_account.status = SchemeAccount.ACTIVE
            scheme_account.save(update_fields=['status'])

            HistoricalSchemeAccount(
                change_type=HistoricalSchemeAccount.UPDATE,
                instance_id=scheme_account.id,
                change_details='status',
                body={"id": scheme_account.id, "status": SchemeAccount.ACTIVE},
                channel=self.barclays_channel
            ).save()

        three_hours_plus = timezone.now() + timedelta(hours=3)
        with mock.patch('django.utils.timezone.now', mock.Mock(return_value=three_hours_plus)):
            test_notification = NotificationProcessor(to_date=timezone.now())
            data = test_notification.get_scheme_account_history()

            self.assertEqual(len(data), 1)

            self.assertEqual(data[0][0], self.user_two.external_id)
            self.assertEqual(data[0][2], AUTHORISED)

    def test_multi_wallet_get_scheme_account_history(self):
        HistoricalSchemeAccountEntry(
            instance_id=self.scheme_account_entry.id,
            change_type=HistoricalSchemeAccount.CREATE,
            scheme_account_id=self.scheme_account.id,
            user_id=self.scheme_account_entry.user.id,
            channel=self.barclays_channel
        ).save()

        HistoricalSchemeAccountEntry(
            instance_id=self.scheme_account_entry_two.id,
            change_type=HistoricalSchemeAccount.CREATE,
            scheme_account_id=self.scheme_account.id,
            user_id=self.scheme_account_entry_two.user.id,
            channel=self.barclays_channel
        ).save()

        HistoricalSchemeAccount(
            change_type=HistoricalSchemeAccount.CREATE,
            instance_id=self.scheme_account.id,
            change_details='',
            body={"id": self.scheme_account.id, "status": SchemeAccount.PENDING},
            channel=self.barclays_channel
        ).save()

        with mock.patch('django.utils.timezone.now', mock.Mock(return_value=self.mocked_datetime)):
            self.scheme_account.status = SchemeAccount.ACTIVE
            self.scheme_account.save(update_fields=['status'])

            HistoricalSchemeAccount(
                change_type=HistoricalSchemeAccount.UPDATE,
                instance_id=self.scheme_account.id,
                change_details='status',
                body={"id": self.scheme_account.id, "status": SchemeAccount.ACTIVE},
                channel=self.barclays_channel
            ).save()

        three_hours_plus = timezone.now() + timedelta(hours=3)
        with mock.patch('django.utils.timezone.now', mock.Mock(return_value=three_hours_plus)):
            test_notification = NotificationProcessor(to_date=timezone.now())
            data = test_notification.get_scheme_account_history()

            self.assertEqual(len(data), 2)
            self.assertEqual(data[0][0], self.user.external_id)
            self.assertEqual(data[0][2], AUTHORISED)
            self.assertEqual(data[1][0], self.user_two.external_id)
            self.assertEqual(data[1][2], AUTHORISED)

    def test_deleted_scheme_account_get_scheme_account_history(self):
        HistoricalSchemeAccountEntry(
            instance_id=self.scheme_account_entry.id,
            change_type=HistoricalSchemeAccount.CREATE,
            scheme_account_id=self.scheme_account.id,
            user_id=self.scheme_account_entry.user.id,
            channel=self.barclays_channel
        ).save()

        HistoricalSchemeAccountEntry(
            instance_id=self.scheme_account_entry_two.id,
            change_type=HistoricalSchemeAccount.CREATE,
            scheme_account_id=self.scheme_account.id,
            user_id=self.scheme_account_entry_two.user.id,
            channel=self.barclays_channel
        ).save()

        HistoricalSchemeAccount(
            change_type=HistoricalSchemeAccount.CREATE,
            instance_id=self.scheme_account.id,
            change_details='',
            body={"id": self.scheme_account.id, "status": SchemeAccount.PENDING},
            channel=self.barclays_channel
        ).save()

        with mock.patch('django.utils.timezone.now', mock.Mock(return_value=self.mocked_datetime)):
            self.scheme_account.is_deleted = True
            self.scheme_account.save(update_fields=['is_deleted'])

            HistoricalSchemeAccount(
                change_type=HistoricalSchemeAccount.DELETE,
                instance_id=self.scheme_account.id,
                change_details='status',
                body={"id": self.scheme_account.id, "status": SchemeAccount.ACTIVE},
                channel=self.barclays_channel
            ).save()

        three_hours_plus = timezone.now() + timedelta(hours=3)
        with mock.patch('django.utils.timezone.now', mock.Mock(return_value=three_hours_plus)):
            test_notification = NotificationProcessor(to_date=timezone.now())
            data = test_notification.get_scheme_account_history()

            self.assertEqual(len(data), 2)
            self.assertEqual(data[0][0], self.user.external_id)
            self.assertEqual(data[0][2], DELETED)
            self.assertEqual(data[1][0], self.user_two.external_id)
            self.assertEqual(data[1][2], DELETED)

    def test_removed_user_from_scheme_get_deleted_scheme_account_entry_history(self):
        HistoricalSchemeAccountEntry(
            instance_id=self.scheme_account_entry.id,
            change_type=HistoricalSchemeAccount.CREATE,
            scheme_account_id=self.scheme_account.id,
            user_id=self.scheme_account_entry.user.id,
            channel=self.barclays_channel
        ).save()

        HistoricalSchemeAccountEntry(
            instance_id=self.scheme_account_entry_two.id,
            change_type=HistoricalSchemeAccount.CREATE,
            scheme_account_id=self.scheme_account.id,
            user_id=self.scheme_account_entry_two.user.id,
            channel=self.barclays_channel
        ).save()

        HistoricalSchemeAccount(
            change_type=HistoricalSchemeAccount.CREATE,
            instance_id=self.scheme_account.id,
            change_details='',
            body={"id": self.scheme_account.id, "status": SchemeAccount.PENDING},
            channel=self.barclays_channel
        ).save()

        with mock.patch('django.utils.timezone.now', mock.Mock(return_value=self.mocked_datetime)):
            HistoricalSchemeAccountEntry(
                instance_id=self.scheme_account_entry_two.id,
                change_type=HistoricalSchemeAccount.DELETE,
                scheme_account_id=self.scheme_account.id,
                user_id=self.scheme_account_entry_two.user.id,
                channel=self.barclays_channel
            ).save()

        three_hours_plus = timezone.now() + timedelta(hours=3)
        with mock.patch('django.utils.timezone.now', mock.Mock(return_value=three_hours_plus)):
            test_notification = NotificationProcessor(to_date=timezone.now())
            data = test_notification.get_deleted_scheme_account_entry_history()

            self.assertEqual(len(data), 1)
            self.assertEqual(data[0][0], self.user_two.external_id)
            self.assertEqual(data[0][2], DELETED)

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
