from azure.storage.blob import BlobServiceClient
from celery import shared_task
from django.conf import settings

from payment_card.models import PaymentCardAccount
from scripts.actions.paymentaccount_actions import PaymentAccountCorrection
from scripts.find_errors.base_script import BaseScript


@shared_task()
def process_files(container_name: str, file_list: list):
    from scripts.scripts import SCRIPT_TITLES, DataScripts

    blob_service_client = BlobServiceClient.from_connection_string(settings.AZURE_CONNECTION_STRING)
    container_client = blob_service_client.get_container_client(container_name)
    failures = []
    item_no = 0
    for upload_file in file_list:
        line_no = 0
        contents = str(container_client.download_blob(upload_file).readall(), "utf-8").split("\n")
        script_id = DataScripts.BARCLAYS_HASH_UPLOAD.value
        correction_script = BaseScript(script_id, SCRIPT_TITLES[script_id])
        correction_script.set_correction(PaymentAccountCorrection.UPDATE_CARD_HASH)
        for hash_pair in contents:
            line_no += 1
            item_no += 1
            if len(hash_pair) > 1:
                old_hash, new_hash = hash_pair.split(",")
                print(old_hash, new_hash)
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
                                "status": account.status,
                                "upload_file": upload_file,
                                "line_no": line_no,
                                "item_no": item_no,
                            },
                        )

                except Exception as ex:
                    print(f"Exception {ex}")
                    failures.append(f"{old_hash},{new_hash},{upload_file},{line_no},{item_no},{ex}")
        if failures:
            failed_file = upload_file.replace("hash-files/", "hash-file-failures/failed_")
            blob = container_client.get_blob_client(failed_file)
            data = "\n".join(failures)
            blob.upload_blob(data)
        else:
            success_file = upload_file.replace("hash-files/", "hash-file-success/success_")
            blob = container_client.get_blob_client(success_file)
            data = f'{upload_file},{line_no},{item_no},"all read in for corrections"\n'
            blob.upload_blob(data)
        # todo: Now move file from imports to archive:
