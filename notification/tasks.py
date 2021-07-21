import csv
import logging
from datetime import timedelta
from time import time, sleep

import pysftp
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from paramiko import SSHException
from pysftp import Connection, ConnectionException

from history.models import HistoricalSchemeAccount
from scheme.models import SchemeAccount
from ubiquity.models import SchemeAccountEntry


logger = logging.getLogger(__name__)

STATUS_MAP = {x[0]: x[1] for x in SchemeAccount.EXTENDED_STATUSES}


class SftpManager:
    def __init__(self, rows=None):
        self.host = settings.SFTP_HOST
        self.sftp_username = settings.SFTP_USERNAME
        self.sftp_password = settings.SFTP_PASSWORD
        self.rows = rows
        self.cnopts = pysftp.CnOpts()

    @staticmethod
    def format_data(data):
        return [['01', x[0], x[1], STATUS_MAP[x[2]], x[3].timestamp()] for x in data]

    def transfer_file(self):
        date = timezone.now().strftime('%Y%m%d')
        timestamp = int(time())
        filename = f'Bink_lc_status_{timestamp}_{date}.csv'
        rows = self.format_data(self.rows)

        errors = 0

        while True:
            try:
                with Connection(
                        self.host,
                        username=self.sftp_username,
                        password=self.sftp_password,
                        cnopts=self.cnopts
                ) as sftp:
                    logging.info('Successfully connected to SFTP.')
                    with sftp.open(filename, 'w', bufsize=32768) as f:
                        writer = csv.writer(f)
                        writer.writerow([00, date])
                        writer.writerows(self.rows)
                        writer.writerow([99, len(rows)])
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
    def __init__(self, organisation, to_date=None):
        self.org = organisation
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
                'scheme_account__scheme__name',
                'scheme_account__status',
                'scheme_account__created'
            )
        else:
            # Zero out provided time
            to_datetime = self.to_date.replace(microsecond=0, second=0, minute=0)

            # Get any status changes in the last 2 hours where status has changed
            from_datetime = to_datetime - timedelta(hours=2)
            list_of_ids = list(scheme_accounts_entries.values_list('scheme_account_id', flat=True))
            historical_rows = list(HistoricalSchemeAccount.objects.filter(
                instance_id__in=list_of_ids,
                change_details__contains=change_type,
                created__range=[from_datetime, to_datetime]
            ).values('instance_id', 'body', 'created'))

            # Need the values from SchemeAccount and the created date from HistoricalSchemeAccount
            if historical_rows:
                ids_to_filter = [row["instance_id"] for row in historical_rows]
                rows = scheme_accounts_entries.filter(scheme_account_id__in=ids_to_filter).values(
                    'scheme_account_id',
                    'user__external_id',
                    'scheme_account__scheme__name',
                    'scheme_account__status',
                )

                for row in rows:
                    for counter, value in enumerate(historical_rows):
                        if int(value['instance_id']) == row['scheme_account_id']:
                            rows_to_write.append([
                                row['user__external_id'],
                                row['scheme_account__scheme__name'],
                                value['body']['status'],
                                value['created']
                            ])

                            # Remove from list so we don't have to loop through it again
                            historical_rows.pop(counter)

                            break

        return rows_to_write


@shared_task()
def notification_file(organisation="Barclays", to_time=None):
    notification = NotificationProcessor(organisation=organisation, to_time=to_time)
    data_to_write = notification.get_data()

    if data_to_write:
        logger.info("Connecting to SFTP to write csv.")
        sftp = SftpManager()
        sftp.transfer_file()
