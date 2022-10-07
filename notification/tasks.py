import csv
import datetime
import logging
import operator
import os
from io import StringIO
from time import sleep, time

import paramiko
from celery import shared_task
from django.conf import settings
from django.utils import timezone

from history.models import HistoricalBase, HistoricalSchemeAccount, HistoricalSchemeAccountEntry
from notification import stfp_connect
from scheme.models import SchemeAccount
from ubiquity.channel_vault import BarclaysSftpKeyNames, get_barclays_sftp_key, load_secrets
from ubiquity.models import AccountLinkStatus, SchemeAccountEntry
from ubiquity.reason_codes import DELETED, ubiquity_status_translation
from user.models import CustomUser

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
        return [["01", x[0], x[1], ubiquity_status_translation.get(x[2], x[2]), int(x[3].timestamp())] for x in data]

    @staticmethod
    def remove_duplicates(data):
        # Removed matching duplicates using set and then sort the list by latest
        removed_duplicates = sorted(set(map(tuple, data)), key=operator.itemgetter(1, 2, 4), reverse=True)
        cleansed_data = []

        # Remove duplicates that resulted from looking at the HistoricalSchemeAccount and
        # HistoricalSchemeAccountEntry. Won't be removed from the above because they might have
        # a different timestamp. This only happens when a user is added to a loyalty card and then the
        # status change and we only want the latest entry.
        for x in removed_duplicates:
            if not cleansed_data:
                cleansed_data.append(list(x))
            else:
                if x[1] == cleansed_data[-1][1] and x[2] == cleansed_data[-1][2]:
                    continue
                else:
                    cleansed_data.append(list(x))

        return cleansed_data

    def connect(self):
        # custom_paramiko.HostKey, takes host, keytype, key hence **item works
        host_keys = [stfp_connect.HostKey(**item) for item in self.sftp_host_keys]
        return stfp_connect.get_sftp_client(
            host=self.host,
            port=self.port,
            username=self.sftp_username,
            password=self.sftp_password,
            pkey=self.sftp_private_key_string,
            host_keys=host_keys,
        )

    def transfer_file(self):
        date = timezone.now().strftime("%Y%m%d")
        timestamp = int(time())
        filename = f"Bink_lc_status_{timestamp}_{date}.csv{settings.BARCLAYS_SFTP_FILE_SUFFIX}"
        rows = self.remove_duplicates(self.format_data(self.rows))

        logger.warning("Establishing connection with SFTP.")
        sftp_client = self.connect()
        logger.warning("Connection established.")

        try:
            with sftp_client.open(os.path.join(settings.SFTP_DIRECTORY, filename), "w", bufsize=32768) as f:
                logger.warning("Writing file.")
                writer = csv.writer(f)
                writer.writerow(["00", date])
                writer.writerows(rows)
                writer.writerow([99, f"{len(rows):010}"])
                logging.warning(f"File: {filename}, uploaded.")
        except FileNotFoundError as e:
            logger.exception("File not found.")
            raise e

        sftp_client.close()
        logger.warning("Connection closed")
        return


class NotificationProcessor:
    def __init__(self, initiation=True):
        self.client_application_name = "Barclays Mobile Banking"
        self.channel = "com.barclays.bmb"
        self.initiation = initiation
        self.to_date = timezone.now()
        self.change_type = "status"

        run_times = settings.NOTIFICATION_RUN_TIME.split(",")

        # if first run of the day we want all the changes that happened outside of the specified hours
        if self.to_date.time() < datetime.time(int(run_times[1])):
            previous_day = self.to_date - datetime.timedelta(days=1)
            self.from_datetime = previous_day.replace(hour=int(run_times[-1]))
        else:
            self.from_datetime = self.to_date - datetime.timedelta(seconds=settings.NOTIFICATION_PERIOD)

    def check_previous_status(self, scheme_account, from_date, history_obj, deleted=False):
        if deleted:
            query = {
                "instance_id": scheme_account.id,
                "created__lt": from_date,
                "change_type": HistoricalBase.UPDATE,
            }
        else:
            query = {
                "instance_id": scheme_account.id,
                "created__lt": from_date,
            }

        status = None
        state = None
        if history_obj.change_type == HistoricalBase.CREATE:
            status = AccountLinkStatus.PENDING
        elif history_obj.change_type == HistoricalBase.DELETE:
            status = DELETED
        else:
            if self.change_type in history_obj.change_details:
                status = history_obj.link_status

        if status is not None:
            state = self.get_status_translation(scheme_account, status)
        else:
            state = None

        history = HistoricalSchemeAccountEntry.objects.filter(**query).last()

        if history:
            previous_state = self.get_status_translation(scheme_account, history.link_status)
            if state == previous_state:
                state = None

        return state

    @staticmethod
    def get_status_translation(scheme_account, status):
        if status == DELETED:
            state = DELETED
        else:
            if status in AccountLinkStatus.system_action_required():
                if scheme_account.balances:
                    state = ubiquity_status_translation[AccountLinkStatus.ACTIVE]
                else:
                    state = ubiquity_status_translation[AccountLinkStatus.PENDING]
            else:
                state = ubiquity_status_translation.get(status, status)

        return state

    def get_scheme_account_history(self):
        data = []

        barclays_scheme_account_entries = SchemeAccountEntry.objects.filter(
            user__client__name=self.client_application_name,
            scheme_account__updated__gte=self.from_datetime,
            scheme_account__updated__lte=self.to_date,
        )

        for scheme_association in barclays_scheme_account_entries:
            history_data = HistoricalSchemeAccountEntry.objects.filter(
                instance_id=scheme_association.scheme_account_id,
                created__range=[self.from_datetime, self.to_date]
            ).last()

            if history_data:
                state = self.check_previous_status(
                    scheme_association.scheme_account,
                    self.from_datetime,
                    history_data
                )

                if state:
                    data.append(
                        [
                            scheme_association.user.external_id,
                            scheme_association.scheme_account.scheme.slug,
                            state,
                            history_data.created
                        ]
                    )

        # for scheme_association in barclays_scheme_account_entries:
        #     history_data = HistoricalSchemeAccount.objects.filter(
        #         instance_id=scheme_association.scheme_account_id,
        #         created__range=[self.from_datetime, self.to_date],
        #         change_details__contains="status",
        #     ).last()
        #
        #     if history_data:
        #         state = self.check_previous_status(
        #             scheme_association.scheme_account,
        #             self.from_datetime,
        #             history_data,
        #         )
        #
        #         if state:
        #             data.append(
        #                 [
        #                     scheme_association.user.external_id,
        #                     scheme_association.scheme_account.scheme.slug,
        #                     state,
        #                     history_data.created,
        #                 ]
        #             )

        return data

    def get_scheme_account_entry_history(self):
        data = []
        deleted_user_id_assocations = []

        # Sort queryset by user_id and created time to see if delete is the latest status
        historical_scheme_account_association = HistoricalSchemeAccountEntry.objects.filter(
            channel=self.channel, created__range=[self.from_datetime, self.to_date]
        ).order_by("user_id", "-created")

        for association in historical_scheme_account_association:
            # If the user association has already been removed then skip to next item
            if [association.user_id, association.scheme_account_id] in deleted_user_id_assocations:
                continue

            scheme_account = SchemeAccount.all_objects.filter(id=association.scheme_account_id)
            user = CustomUser.all_objects.filter(id=association.user_id)

            # if scheme_account and user:
            if association.change_type == HistoricalBase.DELETE:
                # Delete row
                data.append([user[0].external_id, scheme_account[0].scheme.slug, DELETED, association.created])

                deleted_user_id_assocations.append([association.user_id, association.scheme_account_id])

            else:
                # Gets the current status when the loyalty card is added to another wallet
                data.append(
                    [
                        user[0].external_id,
                        scheme_account[0].scheme.slug,
                        self.get_status_translation(scheme_account[0], association.link_status),
                        association.created,
                    ]
                )

        return data

    def get_data(self):
        rows_to_write = []

        # initiation file data
        if self.initiation:
            # Get all barclays scheme account associations
            scheme_accounts_entries = SchemeAccountEntry.objects.filter(user__client__name=self.client_application_name)

            rows_to_write = scheme_accounts_entries.values_list(
                "user__external_id", "scheme_account__scheme__slug", "link_status", "scheme_account__created"
            )

        else:
            historical_scheme_accounts = self.get_scheme_account_history()
            historical_scheme_account_association = self.get_scheme_account_entry_history()

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
                logging.warning("Retrying connection to SFTP.")
                sleep(settings.NOTIFICATION_RETRY_TIMER)
                if retry_count == settings.NOTIFICATION_ERROR_THRESHOLD:
                    logging.exception(f"Failed to connect. Error - {e}")
                    raise e
