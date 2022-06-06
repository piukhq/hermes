import string
from datetime import datetime

from azure.storage.blob import BlobServiceClient
from celery import shared_task
from django.conf import settings
from shared_config_storage.credentials.encryption import BLAKE2sHash

from payment_card.models import PaymentCardAccount
from scripts.actions.paymentaccount_actions import PaymentAccountCorrection
from scripts.find_errors.base_script import BaseScript
from ubiquity.channel_vault import SecretKeyName, get_secret_key


@shared_task()
def process_files(file_list: list):
    from scripts.scripts import SCRIPT_TITLES, DataScripts

    now = datetime.now()
    now_str = now.strftime("%H%M")
    date_str = now.strftime("%Y/%m/%d/")
    blob_service_client = BlobServiceClient.from_connection_string(settings.AZURE_CONNECTION_STRING)
    container_client = blob_service_client.get_container_client(settings.UPLOAD_CONTAINER_NAME)
    archive_client = blob_service_client.get_container_client(settings.ARCHIVE_CONTAINER_NAME)
    item_no = 0
    remove_white_space = str.maketrans("", "", string.whitespace)
    for upload_file in file_list:
        failures = []
        line_no = 0
        archive_file = date_str + upload_file.replace("hash-files/", f"processed_{now_str}/imported/")
        bytes_io = container_client.download_blob(upload_file).readall()
        archive_client.get_blob_client(archive_file).upload_blob(bytes_io)
        contents = str(bytes_io, "utf-8").split("\n")
        script_id = DataScripts.BARCLAYS_HASH_UPLOAD.value
        correction_script = BaseScript(script_id, SCRIPT_TITLES[script_id])
        correction_script.set_correction(PaymentAccountCorrection.UPDATE_CARD_HASH)
        for hash_pair in contents:
            hash_pair.translate(remove_white_space)
            if len(hash_pair) > 1:
                line_no += 1
                item_no += 1
                ext_old_hash, ext_new_hash = hash_pair.split(",")
                key_hash = get_secret_key(SecretKeyName.PCARD_HASH_SECRET)
                old_hash = BLAKE2sHash().new(obj=ext_old_hash, key=key_hash)
                new_hash = BLAKE2sHash().new(obj=ext_new_hash, key=key_hash)

                try:
                    account = PaymentCardAccount.objects.get(hash=old_hash)
                    if account and account.hash == old_hash:
                        correction_script.set_correction(PaymentAccountCorrection.UPDATE_CARD_HASH)
                        correction_script.make_correction(
                            str(account.id),
                            {
                                "payment_card_account_id": account.id,
                                "old_hash": old_hash,
                                "new_hash": new_hash,
                                "ext_old_hash": ext_old_hash,
                                "ext_new_hash": ext_new_hash,
                                "status": account.status,
                                "upload_file": upload_file,
                                "line_no": line_no,
                                "item_no": item_no,
                            },
                        )

                except Exception as ex:
                    failures.append(f"{ext_old_hash},{ext_new_hash},{upload_file},{line_no},{item_no},{ex}")
        if failures:
            failed_file = archive_file.replace("imported/", "failures/failed_")
            data = "\n".join(failures)
            archive_client.get_blob_client(failed_file).upload_blob(data)
        else:
            success_file = archive_file.replace("imported/", "success/success_")
            data = f'{upload_file},{line_no},{item_no},"all read in for corrections"\n'
            archive_client.get_blob_client(success_file).upload_blob(data)
        # Now delete file from imports to archive:
        container_client.get_blob_client(upload_file).delete_blob()
