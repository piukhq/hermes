import csv
import logging
from datetime import timedelta
from io import StringIO
from time import time, sleep

import pysftp
from base64 import b64decode
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from paramiko import SSHException, RSAKey, Ed25519Key
from pysftp import Connection, ConnectionException

from user.models import CustomUser
from history.models import HistoricalBase, HistoricalSchemeAccount, HistoricalSchemeAccountEntry
from scheme.models import SchemeAccount
from ubiquity.channel_vault import load_secrets, get_barclays_sftp_key, BarclaysSftpKeyNames
from ubiquity.models import SchemeAccountEntry
from ubiquity.reason_codes import ubiquity_status_translation, DELETED

logger = logging.getLogger(__name__)


class SftpManager:
    def __init__(self, rows=None):
        # load vault secrets
        load_secrets(settings.VAULT_CONFIG)
        self.host = get_barclays_sftp_key(BarclaysSftpKeyNames.SFTP_HOST)
        self.port = get_barclays_sftp_key(BarclaysSftpKeyNames.SFTP_PORT)
        self.sftp_username = get_barclays_sftp_key(BarclaysSftpKeyNames.SFTP_USERNAME)
        self.sftp_password = get_barclays_sftp_key(BarclaysSftpKeyNames.SFTP_PASSWORD)
        self.sftp_private_key_string = RSAKey.from_private_key(
            StringIO(get_barclays_sftp_key(BarclaysSftpKeyNames.SFTP_PRIVATE_KEY))
        )
        self.sftp_host_keys = get_barclays_sftp_key(BarclaysSftpKeyNames.SFTP_HOST_KEYS)

        self.rows = rows

    @staticmethod
    def format_data(data):
        # Format data to return status that match api response and covert date to timestamp
        return [['01', x[0], x[1], ubiquity_status_translation.get(x[2], x[2]), int(x[3].timestamp())] for x in data]

    def transfer_file(self):
        logger.info("Transferring file")
        date = timezone.now().strftime('%Y%m%d')
        timestamp = int(time())
        filename = f'Bink_lc_status_{timestamp}_{date}.csv_{settings.BARCLAYS_SFTP_FILE_SUFFIX}'
        rows = self.format_data(self.rows)
        cnopts = pysftp.CnOpts()

        for host_key in self.sftp_host_keys:
            if host_key['keytype'] == "ssh-rsa":
                cnopts.hostkeys.add(hostname=host_key['host'],
                                    keytype=host_key['keytype'],
                                    key=RSAKey(data=b64decode(host_key['key'])))
            elif host_key['keytype'] == "ssh-ed25519":
                cnopts.hostkeys.add(hostname=host_key['host'],
                                    keytype=host_key['keytype'],
                                    key=Ed25519Key(data=b64decode(host_key['key'])))
                pass

        errors = 0

        while True:
            try:
                with Connection(
                    self.host,
                    port=self.port,
                    username=self.sftp_username,
                    password=self.sftp_password,
                    private_key=self.sftp_private_key_string,
                    cnopts=cnopts
                ) as sftp:
                    logger.info('Connected to sftp')
                    with sftp.open(f"{settings.SFTP_DIRECTORY}{filename}", 'w', bufsize=32768) as f:
                        writer = csv.writer(f)
                        writer.writerow(["00", date])
                        writer.writerows(rows)
                        writer.writerow([99, f"{len(rows):010}"])
                    logging.info(f'File: {filename}, uploaded.')
                    return
            except (ConnectionException, SSHException) as e:
                errors += 1
                logging.info('Retrying notification file in 2 minutes.')
                sleep(settings.NOTIFICATION_RETRY_TIMER)
                if errors == settings.NOTIFICATION_ERROR_THRESHOLD:
                    logging.exception(f'Failed to transfer file. Error - {e}')
                    raise e


class NotificationProcessor:
    def __init__(self, to_date=None):
        self.client_application_name = 'Barclays Mobile Banking'
        self.channel = 'com.barclays.bmb'
        self.to_date = to_date
        self.change_type = 'status'

    def check_previous_status(self, scheme_account, from_date, history_obj, deleted=False):
        if deleted:
            query = {
                "instance_id": scheme_account.id,
                "created__lt": from_date,
                "change_details__in": self.change_type,
                "change_type": HistoricalBase.UPDATE
            }
        else:
            query = {
                "instance_id": scheme_account.id,
                "created__lt": from_date,
            }

        status = None
        state = None
        if history_obj.change_type == HistoricalBase.CREATE:
            status = SchemeAccount.PENDING
        elif history_obj.change_type == HistoricalBase.DELETE:
            status = DELETED
        else:
            if self.change_type in history_obj.change_details:
                status = history_obj.body['status']

        if status is not None:
            state = self.get_status_translation(scheme_account, status)
        else:
            state = None

        history = HistoricalSchemeAccount.objects.filter(**query).last()

        if history:
            previous_state = self.get_status_translation(scheme_account, history.body["status"])
            if state == previous_state:
                state = None

        return state

    @staticmethod
    def get_status_translation(scheme_account, status):
        if status == DELETED:
            state = DELETED
        else:
            if status in SchemeAccount.SYSTEM_ACTION_REQUIRED:
                if scheme_account.balances:
                    state = ubiquity_status_translation[scheme_account.ACTIVE]
                else:
                    state = ubiquity_status_translation[scheme_account.PENDING]
            else:
                state = ubiquity_status_translation.get(status, status)

        return state

    def get_scheme_account_history(self):
        data = []
        from_datetime = self.to_date - timedelta(seconds=settings.NOTIFICATION_PERIOD)

        barclays_scheme_account_entries = SchemeAccountEntry.objects.filter(
            user__client__name=self.client_application_name,
            scheme_account__updated__range=[from_datetime, self.to_date]
        )

        for scheme_association in barclays_scheme_account_entries:
            history_data = HistoricalSchemeAccount.objects.filter(
                instance_id=scheme_association.scheme_account_id,
                created__range=[from_datetime, self.to_date]
            )

            for history in history_data:
                state = self.check_previous_status(
                    scheme_association.scheme_account,
                    from_datetime,
                    history,
                )

                if state:
                    data.append([
                        scheme_association.user.external_id,
                        scheme_association.scheme_account.scheme.slug,
                        state,
                        history.created
                    ])

        return data

    def get_deleted_scheme_account_entry_history(self):
        # Get removed users from scheme accounts
        data = []
        from_datetime = self.to_date - timedelta(seconds=settings.NOTIFICATION_PERIOD)

        historical_scheme_account_association = HistoricalSchemeAccountEntry.objects.filter(
            channel=self.channel,
            change_type=HistoricalBase.DELETE,
            created__range=[from_datetime, self.to_date]
        )

        for association in historical_scheme_account_association:
            scheme_account = SchemeAccount.all_objects.filter(id=association.scheme_account_id)
            user = CustomUser.all_objects.filter(id=association.user_id)

            if scheme_account and user:
                history_data = HistoricalSchemeAccount.objects.filter(
                    instance_id=scheme_account[0].id,
                    created__range=[from_datetime, self.to_date]
                )

                for history in history_data:
                    state = self.check_previous_status(
                        scheme_account[0],
                        from_datetime,
                        history,
                    )

                    # History prior deletion
                    if state:
                        data.append([
                            user[0].external_id,
                            scheme_account[0].scheme.slug,
                            state,
                            history.created
                        ])

                # Delete row
                data.append([
                    user[0].external_id,
                    scheme_account[0].scheme.slug,
                    DELETED,
                    association.created
                ])

        return data

    def get_data(self):
        rows_to_write = []

        # Get all barclays scheme account associations
        scheme_accounts_entries = SchemeAccountEntry.objects.filter(
            user__client__name=self.client_application_name)

        # initiation file data
        if not self.to_date:
            rows_to_write = scheme_accounts_entries.values_list(
                'user__external_id',
                'scheme_account__scheme__slug',
                'scheme_account__status',
                'scheme_account__created'
            )

        else:
            if settings.NOTIFICATION_RUN:
                historical_scheme_accounts = self.get_scheme_account_history()
                historical_scheme_account_association = self.get_deleted_scheme_account_entry_history()

                rows_to_write = historical_scheme_accounts + historical_scheme_account_association

        return rows_to_write


@shared_task
def notification_file(to_date=None):
    notification = NotificationProcessor(to_date=to_date)
    data_to_write = notification.get_data()

    logger.info("Connecting to SFTP to write csv.")
    sftp = SftpManager(rows=data_to_write)
    sftp.transfer_file()
