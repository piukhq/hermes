import csv
import logging
from datetime import timedelta
from io import StringIO
from time import time, sleep

import pysftp
from base64 import b64decode
from celery import shared_task
from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from paramiko import SSHException, RSAKey, Ed25519Key
from pysftp import Connection, ConnectionException

from user.models import CustomUser
from history.models import HistoricalBase, HistoricalSchemeAccount, HistoricalSchemeAccountEntry
from scheme.models import SchemeAccount
from ubiquity.channel_vault import load_secrets, get_barclays_sftp_key, BarclaysSftpKeyNames
from ubiquity.models import SchemeAccountEntry
from ubiquity.reason_codes import ubiquity_status_translation

logger = logging.getLogger(__name__)


class SftpManager:
    def __init__(self, rows=None):
        # load vault secrets
        load_secrets(settings.VAULT_CONFIG)
        self.host = get_barclays_sftp_key(BarclaysSftpKeyNames.SFTP_HOST)
        self.sftp_username = get_barclays_sftp_key(BarclaysSftpKeyNames.SFTP_USERNAME)
        self.sftp_private_key_string = RSAKey.from_private_key(
            StringIO(get_barclays_sftp_key(BarclaysSftpKeyNames.SFTP_PRIVATE_KEY))
        )
        self.sftp_host_keys = get_barclays_sftp_key(BarclaysSftpKeyNames.SFTP_HOST_KEYS)

        self.rows = rows

    @staticmethod
    def format_data(data):
        # Format data to return status that match api response and covert date to timestamp
        return [
            ['01', x[0], x[1], ubiquity_status_translation.get(x[2], x[2]), int(x[3].timestamp())] for x in data
        ]

    def transfer_file(self):
        logger.info("Transferring file")
        date = timezone.now().strftime('%Y%m%d')
        timestamp = int(time())
        filename = f'Bink_lc_status_{timestamp}_{date}.csv'
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
                        username=self.sftp_username,
                        private_key=self.sftp_private_key_string,
                        cnopts=cnopts
                ) as sftp:
                    logger.info('Connected to sftp')
                    with sftp.open(f"{settings.SFTP_DIRECTORY}/{filename}", 'w', bufsize=32768) as f:
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
                    logging.warning(f'Failed to transfer file. Error - {e}')
                    raise e


class NotificationProcessor:
    def __init__(self, to_date=None):
        self.org = 'Barclays'
        self.channel = 'com.barclays.bmb'
        self.to_date = to_date

    def get_data(self):
        rows_to_write = []
        change_type = 'status'

        scheme_accounts_entries = SchemeAccountEntry.objects.filter(
            user__client__organisation__name=self.org
        )

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
                from_datetime = self.to_date - timedelta(seconds=settings.NOTIFICATION_PERIOD)

                barclays_scheme_accounts = scheme_accounts_entries.values(
                    'scheme_account_id',
                    'user__external_id',
                    'scheme_account__scheme__slug',
                    'scheme_account__status',
                )

                ids_to_filter = [row["scheme_account_id"] for row in barclays_scheme_accounts]

                # Get all status changes for barclays wallets (created and updated)
                historical_scheme_account_data = HistoricalSchemeAccount.objects.filter(
                    Q(change_details__contains=change_type) |
                    Q(change_details=''),
                    instance_id__in=ids_to_filter,
                    created__range=[from_datetime, self.to_date],
                ).values('instance_id', 'body', 'created')

                # Get deleted
                historical_scheme_account_entry_data = HistoricalSchemeAccountEntry.objects.filter(
                    change_type=HistoricalBase.DELETE,
                    channel=self.channel,
                    created__range=[from_datetime, self.to_date],
                ).values('user_id', 'scheme_account_id', 'created')

                if historical_scheme_account_data:
                    for data in historical_scheme_account_data:
                        for row in barclays_scheme_accounts:
                            if int(data['instance_id']) == row['scheme_account_id']:
                                rows_to_write.append([
                                    row['user__external_id'],
                                    row['scheme_account__scheme__slug'],
                                    data['body']['status'],
                                    data['created']
                                ])

                                break

                if historical_scheme_account_entry_data:
                    for historical_data in historical_scheme_account_entry_data:
                        user = CustomUser.objects.get(id=historical_data['user_id'])
                        scheme_account = SchemeAccount.objects.get(id=historical_data['scheme_account_id'])

                        rows_to_write.append([
                            user.external_id,
                            scheme_account.scheme.slug,
                            'deleted',
                            historical_data['created']
                        ])

        return rows_to_write


@shared_task
def notification_file(to_date=None):
    notification = NotificationProcessor(to_date=to_date)
    data_to_write = notification.get_data()

    if data_to_write:
        logger.info("Connecting to SFTP to write csv.")
        sftp = SftpManager(rows=data_to_write)
        sftp.transfer_file()
