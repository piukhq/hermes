import csv
import logging
import os
from datetime import timedelta
from io import StringIO
from time import time, sleep

import paramiko
from celery import shared_task
from django.conf import settings
from django.utils import timezone

from user.models import CustomUser
from history.models import HistoricalBase, HistoricalSchemeAccount, HistoricalSchemeAccountEntry
from notification import stfp_connect
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
        self.sftp_private_key_string = paramiko.RSAKey.from_private_key(
            StringIO(get_barclays_sftp_key(BarclaysSftpKeyNames.SFTP_PRIVATE_KEY))
        )
        self.sftp_host_keys = get_barclays_sftp_key(BarclaysSftpKeyNames.SFTP_HOST_KEYS)

        self.rows = rows

    @staticmethod
    def format_data(data):
        # Format data to return status that match api response and covert date to timestamp
        return [['01', x[0], x[1], ubiquity_status_translation.get(x[2], x[2]), int(x[3].timestamp())] for x in data]

    def connect(self):
        # custom_paramiko.HostKey, takes host, keytype, key hence **item works
        host_keys = [stfp_connect.HostKey(**item) for item in self.sftp_host_keys]
        return stfp_connect.get_sftp_client(
            host=self.host, port=self.port, username=self.sftp_username, password=self.sftp_password,
            pkey=self.sftp_private_key_string, host_keys=host_keys)

    def transfer_file(self):
        date = timezone.now().strftime('%Y%m%d')
        timestamp = int(time())
        filename = f'Bink_lc_status_{timestamp}_{date}.csv{settings.BARCLAYS_SFTP_FILE_SUFFIX}'
        rows = self.format_data(self.rows)

        logger.info('Establishing connection with SFTP.')
        sftp_client = self.connect()
        logger.info('Connection established.')

        try:
            with sftp_client.open(os.path.join(settings.SFTP_DIRECTORY, filename), 'w', bufsize=32768) as f:
                logger.info('Writing file.')
                writer = csv.writer(f)
                writer.writerow(["00", date])
                writer.writerows(rows)
                writer.writerow([99, f"{len(rows):010}"])
                logging.info(f'File: {filename}, uploaded.')
        except FileNotFoundError as e:
            logger.exception("File not found.")
            raise e

        sftp_client.close()
        logger.info('Connection closed')
        return


class NotificationProcessor:
    def __init__(self, initiation=True):
        self.client_application_name = 'Barclays Mobile Banking'
        self.channel = 'com.barclays.bmb'
        self.initiation = initiation
        self.to_date = timezone.now()
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
            scheme_account__updated__gte=from_datetime,
            scheme_account__updated__lte=self.to_date
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
        if self.initiation:
            rows_to_write = scheme_accounts_entries.values_list(
                'user__external_id',
                'scheme_account__scheme__slug',
                'scheme_account__status',
                'scheme_account__created'
            )

        else:
            historical_scheme_accounts = self.get_scheme_account_history()
            historical_scheme_account_association = self.get_deleted_scheme_account_entry_history()

            rows_to_write = historical_scheme_accounts + historical_scheme_account_association

        return rows_to_write


@shared_task
def notification_file(initiation=True):
    retry_count = 0
    if settings.NOTIFICATION_RUN:
        notification = NotificationProcessor(initiation=initiation)
        data_to_write = notification.get_data()

        sftp = SftpManager(rows=data_to_write)

        while True:
            try:
                sftp.transfer_file()
                return
            except Exception as e:
                retry_count += 1
                logging.warning('Retrying connection to SFTP.')
                sleep(settings.NOTIFICATION_RETRY_TIMER)
                if retry_count == settings.NOTIFICATION_ERROR_THRESHOLD:
                    logging.exception(f'Failed to connect. Error - {e}')
                    raise e
