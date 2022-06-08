import string

from celery import shared_task
from shared_config_storage.credentials.encryption import BLAKE2sHash

from payment_card.models import PaymentCardAccount
from scripts.find_errors.base_script import BaseScript
from ubiquity.channel_vault import SecretKeyName, get_secret_key

from ..actions.corrections import Correction
from ..azure_files import process_files


def process_barclays_hash_contents(upload_file, contents, item_no):
    from scripts.scripts import SCRIPT_TITLES, DataScripts

    failures = []
    line_no = 0
    remove_white_space = str.maketrans("", "", string.whitespace)
    script_id = DataScripts.BARCLAYS_HASH_UPLOAD.value
    correction_script = BaseScript(script_id, SCRIPT_TITLES[script_id])
    correction_script.set_correction(Correction.UPDATE_CARD_HASH)
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
                    correction_script.set_correction(Correction.UPDATE_CARD_HASH)
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
    return failures, item_no


def process_barclays_delete_contents(upload_file, contents, item_no):
    failures = []
    return failures, item_no


@shared_task()
def process_barclays_hash_files(file_list: list):
    process_files(file_list, "hash-files/", process_barclays_hash_contents)


@shared_task()
def process_barclays_delete_files(file_list: list):
    process_files(file_list, "delete-files/", process_barclays_delete_contents)
