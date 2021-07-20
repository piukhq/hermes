import csv
import logging
from datetime import timedelta
from time import time, sleep

from celery import shared_task
from django.conf import settings
from django.utils import timezone
from pysftp import Connection, ConnectionException

from history.models import HistoricalSchemeAccount
from ubiquity.models import SchemeAccountEntry


logger = logging.getLogger(__name__)


class SftpManager:
    def __init__(self, rows=None):
        self.host = settings.SFTP_HOST
        self.sftp_username = settings.SFTP_USERNAME
        self.sftp_password = settings.SFTP_PASSWORD
        self.rows = rows

    @staticmethod
    def format_data(data):
        return [["01", x[0], x[1], x[2], x[3]] for x in data]

    def transfer_file(self):
        date = timezone.now().strftime('%Y%m%d')
        timestamp = int(time())
        filename = f'Bink_lc_status_{timestamp}_{date}.csv'
        rows = self.format_data(self.rows)

        errors = 0
        run = True

        while run:
            try:
                with Connection(self.host, username=self.sftp_username, password=self.sftp_password) as sftp:
                    logging.info("Successfully connected to SFTP.")
                    with sftp.open(filename, 'w', bufsize=32768) as f:
                        writer = csv.writer(f)
                        writer.writerow([00, date])
                        writer.writerows(self.rows)
                        writer.writerow([99, len(rows)])
                        run = False
            except ConnectionException as e:
                logging.info("Retrying notification file in 2 minutes.")
                sleep(120)
                if errors == 5:
                    logging.warning(f"Failed to transfer file. Error - {e}")
                    run = False

        logging.info(f"File: {filename}, uploaded.")


class NotificationProcessor:
    def __init__(self, organisation, to_date=None):
        self.org = organisation
        self.to_date = to_date

    def get_data(self):
        change_type = "status"
        scheme_accounts_entries = SchemeAccountEntry.objects.filter(
            user__client__organisation__name=self.org
        )

        # initiation file data
        if not self.to_date:
            rows = scheme_accounts_entries.values_list(
                'user__external_id',
                'scheme_account__scheme__name',
                'scheme_account__status',
                'scheme_account__created'
            )
        else:
            # Zero out provided time
            to_datetime = self.to_date.replace(microsecond=0, second=0, minute=0)

            # Get data for the last 2 hours
            from_datetime = to_datetime - timedelta(hours=2)
            list_of_ids = scheme_accounts_entries.values_list('scheme_account_id')
            rows = HistoricalSchemeAccount.objects.filter(
                instance_id__in=list_of_ids,
                change_details=change_type,
                created__range=[from_datetime, to_datetime]
            ).values_list(
                'user__external_id',
                'scheme_account__scheme__name',
                'scheme_account__status',
                'scheme_account__created',
            )

        return rows


@shared_task()
def notification_file(organisation="Barclays", to_time=None):
    notification = NotificationProcessor(organisation=organisation, to_time=to_time)
    data_to_write = notification.get_data()

    if data_to_write:
        logger.info("Connecting to SFTP to write csv.")
        sftp = SftpManager()
        sftp.transfer_file()
