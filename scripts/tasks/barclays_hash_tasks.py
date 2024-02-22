import string

from celery import shared_task
from shared_config_storage.credentials.encryption import BLAKE2sHash

from payment_card.models import PaymentCard, PaymentCardAccount
from scripts.actions.corrections import Correction
from scripts.azure_files import process_files
from ubiquity.channel_vault import SecretKeyName, get_secret_key
from ubiquity.models import PaymentCardAccountEntry, PaymentCardSchemeEntry, VopActivation
from user.models import CustomUser


def process_barclays_hash_contents(correction_script: object, upload_file: str, contents: list, item_no: int):
    failures = []
    line_no = 0
    remove_white_space = str.maketrans("", "", string.whitespace)
    correction_script.set_correction(Correction.NO_CORRECTION)
    key_hash = get_secret_key(SecretKeyName.PCARD_HASH_SECRET)
    for hash_pair in contents:
        hash_pair_trans = hash_pair.translate(remove_white_space)
        if len(hash_pair) > 1:
            line_no += 1
            item_no += 1
            ext_old_hash, ext_new_hash = hash_pair_trans.split(",")
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


def select_correction(
    correction_script,
    owners,
    upload_file,
    account,
    user,
    account_user_assoc_id,
    vop,
    active_links,
    activation_data,
    line_no,
    item_no,
):
    if len(owners) == 1:
        if vop:
            correction_script.set_correction(Correction.VOP_REMOVE_DEACTIVATE_AND_DELETE_PAYMENT_ACCOUNT)
        else:
            correction_script.set_correction(Correction.REMOVE_UN_ENROLL_DELETE_PAYMENT_ACCOUNT)
    elif len(owners) > 1:
        correction_script.set_correction(Correction.REMOVE_PAYMENT_ACCOUNT)

    correction_script.make_correction(
        str(account.id),
        {
            "payment_card_account_id": account.id,
            "user_id": user.id,
            "owners": len(owners),
            "account_user_assoc_id": account_user_assoc_id,
            "is_vop": vop,
            "active_links": len(active_links),
            "deactivations": activation_data,
            "status": account.status,
            "upload_file": upload_file,
            "line_no": line_no,
            "item_no": item_no,
        },
    )


def delete_corrections(record, correction_script, upload_file, line_no, item_no, failures):
    # see Jira DM-462 for spec.
    payment_card_account_id, custom_user_id, external_id, created_date, updated_date = record.split(",")
    try:
        error = ""
        vop = False
        activation_data = []
        account = PaymentCardAccount.objects.get(id=payment_card_account_id)
        if account.payment_card.system == PaymentCard.VISA:
            vop = True
            activations = VopActivation.objects.filter(status=VopActivation.ACTIVATING, payment_card_account=account)
            for activation in activations:
                activation_data.append(
                    {
                        "payment_token": account.psp_token,
                        "activation_id": activation.id,
                        "id": account.id,
                    }
                )
        user = CustomUser.objects.get(id=custom_user_id)
        account_user_assoc_id = None
        if user.external_id != external_id:
            error += "External_ids do not match, "
        owners = PaymentCardAccountEntry.objects.filter(payment_card_account=account)
        if len(owners) == 0:
            error += "Not in any wallet, "
        else:
            for owner in owners:
                if owner.user.id == user.id:
                    account_user_assoc_id = owner.id
        if account_user_assoc_id is None:
            error += "Not in user wallet, "

        active_links = PaymentCardSchemeEntry.objects.filter(
            active_link=PaymentCardSchemeEntry.ACTIVE, payment_card_account=account
        )

        if not error:
            select_correction(
                correction_script,
                owners,
                upload_file,
                account,
                user,
                account_user_assoc_id,
                vop,
                active_links,
                activation_data,
                line_no,
                item_no,
            )
        else:
            failures.append(
                f"{payment_card_account_id},{custom_user_id},{external_id},{upload_file},"
                f"{line_no},{item_no},{error}"
            )

    except Exception as ex:
        failures.append(
            f"{payment_card_account_id},{custom_user_id},{external_id},{upload_file},{line_no},{item_no},{ex}"
        )


def process_barclays_delete_contents(correction_script: object, upload_file: str, contents: list, item_no: int):
    failures = []
    line_no = 0
    remove_white_space = str.maketrans("", "", string.whitespace)
    correction_script.set_correction(Correction.NO_CORRECTION)
    for record in contents:
        record.translate(remove_white_space)
        correction_script.set_correction(Correction.NO_CORRECTION)
        if len(record) > 1:
            line_no += 1
            item_no += 1
            # see Jira DM-462 for spec.
            delete_corrections(record, correction_script, upload_file, line_no, item_no, failures)
    return failures, item_no


@shared_task()
def process_barclays_hash_files(correction_script, file_list: list):
    process_files(correction_script, file_list, "hash-files/", process_barclays_hash_contents)


@shared_task()
def process_barclays_delete_files(correction_script, file_list: list):
    process_files(correction_script, file_list, "delete-files/", process_barclays_delete_contents)
