import hashlib
from codecs import getwriter
from csv import DictWriter
from typing import TYPE_CHECKING, cast
from uuid import uuid4

from celery import shared_task
from celery.result import GroupResult
from django.core.files.base import ContentFile
from django.db import transaction
from typing_extensions import TypedDict

from history import models as hm
from payment_card.metis import delete_and_redact_payment_card
from payment_card.models import PaymentCard, PaymentCardAccount
from scheme.models import SchemeAccount, SchemeAccountCredentialAnswer
from scripts.enums import FileScriptStatuses
from scripts.models import FileScript
from ubiquity.models import PaymentCardAccountEntry, PaymentCardSchemeEntry, SchemeAccountEntry
from ubiquity.utils import vop_deactivation_dict_by_payment_card_id
from user.models import CustomUser

if TYPE_CHECKING:

    class SuccessfulType(TypedDict):
        ids: int

    class FailedType(TypedDict):
        ids: int
        reason: str

    class ResultType(TypedDict):
        successful: list[SuccessfulType]
        failed: list[FailedType]

    GroupResultType = list[ResultType]


BytesStreamWriter = getwriter("utf-8")


def write_files_and_status(group_result: "GroupResultType", entry: "FileScript"):
    # have to setup the file as bytes and use a codec to write utf-8 as azure storage only supports bytes file
    failed_file = ContentFile(b"", name=f"FS{entry.id}_failed.csv")
    success_file = ContentFile(b"", name=f"FS{entry.id}_success.csv")

    all_successful = True

    with failed_file.open("wb") as fail_output, success_file.open("wb") as success_output:
        fail_writer = DictWriter(BytesStreamWriter(fail_output), fieldnames=["ids", "reason"])
        success_writer = DictWriter(BytesStreamWriter(success_output), fieldnames=["ids"])
        fail_writer.writeheader()
        success_writer.writeheader()
        for result in group_result:
            if failed := result["failed"]:
                fail_writer.writerows(failed)
                all_successful = False
            if successful := result["successful"]:
                success_writer.writerows(successful)

    description = "Task completed"
    if all_successful:
        description += ", no further action needed."
    else:
        description += ", but with some failures. Check the failed file."

    entry.status = FileScriptStatuses.DONE
    entry.status_description = description
    entry.failed_file = failed_file
    entry.success_file = success_file
    entry.celery_group_id = None
    entry.save(update_fields=["status", "failed_file", "success_file", "status_description", "celery_group_id"])


@shared_task
def right_to_be_forgotten_batch_success_handler_task(group_result: "GroupResultType", *, entry_id: int) -> None:
    entry = FileScript.objects.get(id=entry_id)
    celery_group = GroupResult.restore(entry.celery_group_id)
    write_files_and_status(group_result, entry)
    celery_group.forget()


@shared_task
def right_to_be_forgotten_batch_fail_handler_task(*_args, entry_id: int) -> None:
    entry = FileScript.objects.get(id=entry_id)
    celery_group = GroupResult.restore(entry.celery_group_id)
    group_result: GroupResultType = []
    for result in celery_group.results:
        if result.successful():
            group_result.append(result.get(disable_sync_subtasks=False))
        else:
            group_result.append(
                {
                    "failed": [{"ids": uid, "reason": repr(result.info)} for uid in result.kwargs["ids"]],
                    "successful": [],
                }
            )
            result.forget()

    write_files_and_status(group_result, entry)
    celery_group.forget()


@shared_task
def right_to_be_forgotten_batch_task(ids: list[str], entry_id: int) -> "ResultType":
    result: "ResultType" = {"failed": [], "successful": []}

    for uid in ids:
        success, reason = _right_to_be_forgotten(uid, entry_id)
        if success:
            result["successful"].append({"ids": uid})
        else:
            result["failed"].append({"ids": uid, "reason": reason})

    return result


def _anonymised_value(value: str) -> str:
    return hashlib.sha256((uuid4().hex + value).encode()).hexdigest()


def _forget_user(user: CustomUser) -> None:
    """Anonymise Email and External ID, soft delete user and delete profile and consent."""
    update_fields = ["is_active", "delete_token"]

    if user.email:
        user.email = _anonymised_value(user.email)
        update_fields.append("email")

    if user.external_id:
        user.external_id = _anonymised_value(user.external_id)
        update_fields.append("external_id")

    user.is_active = False
    user.delete_token = uuid4()
    user.save(update_fields=update_fields)

    if hasattr(user, "profile"):
        user.profile.delete()

    if hasattr(user, "serviceconsent"):
        user.serviceconsent.delete()


def _forget_plls(user: CustomUser) -> dict[int, dict]:
    visa_payment_card_id = PaymentCard.objects.values_list("id", flat=True).get(slug="visa")
    pll_to_delete: list[int] = []
    vop_deactivation_map: dict[int, dict] = {}

    plls_ids = user.plluserassociation_set.values_list("pll_id", flat=True)

    for pll in (
        PaymentCardSchemeEntry.objects.filter(id__in=plls_ids)
        .prefetch_related("plluserassociation_set", "payment_card_account")
        .all()
    ):
        if pll.plluserassociation_set.count() > 1:
            # not last man standing. skip rest of logic.
            continue

        # TODO: send midas last man standing event here

        pll_to_delete.append(pll.id)
        if pll.active_link and pll.payment_card_account.payment_card_id == visa_payment_card_id:
            vop_deactivation_map[pll.payment_card_account_id] = vop_deactivation_dict_by_payment_card_id(
                pll.payment_card_account_id
            )

    user.plluserassociation_set.all().delete()
    PaymentCardSchemeEntry.objects.filter(id__in=pll_to_delete).delete()
    return vop_deactivation_map


def _forget_membership_cards(user: CustomUser) -> list[int]:
    updated_mcards: list[SchemeAccount] = []
    links_to_delete: list[int] = []
    for mcard in cast(list[SchemeAccount], user.scheme_account_set.prefetch_related("schemeaccountentry_set").all()):
        links_to_delete.extend(mcard.schemeaccountentry_set.filter(user_id=user.id).values_list("id", flat=True).all())

        if mcard.schemeaccountentry_set.count() > 1:
            # not last man standing. skip rest of logic.
            continue

        if mcard.alt_main_answer:
            mcard.alt_main_answer = _anonymised_value(mcard.alt_main_answer)

        mcard.is_deleted = True
        updated_mcards.append(mcard)

    SchemeAccountCredentialAnswer.objects.filter(scheme_account_entry_id__in=links_to_delete).delete()
    SchemeAccountEntry.objects.filter(id__in=links_to_delete).delete()
    SchemeAccount.all_objects.bulk_update(updated_mcards, fields=["is_deleted", "alt_main_answer"])

    return [card.id for card in updated_mcards]


def _forget_payment_cards(user: CustomUser) -> list[PaymentCardAccount]:
    updated_pcards: list[PaymentCardAccount] = []
    links_to_delete: list[int] = []

    for pcard in cast(
        list[PaymentCardAccount], user.payment_card_account_set.prefetch_related("paymentcardaccountentry_set").all()
    ):
        links_to_delete.extend(
            pcard.paymentcardaccountentry_set.filter(user_id=user.id).values_list("id", flat=True).all()
        )

        if pcard.paymentcardaccountentry_set.count() > 1:
            # not last man standing. skip rest of logic.
            continue

        pcard.name_on_card = _anonymised_value(pcard.name_on_card)
        pcard.is_deleted = True
        updated_pcards.append(pcard)

    PaymentCardAccountEntry.objects.filter(id__in=links_to_delete).delete()
    PaymentCardAccount.all_objects.bulk_update(updated_pcards, fields=["is_deleted", "name_on_card"])

    return updated_pcards


def _forget_history(user_id: int, pcards_ids: list[int], mcards_ids: list[int]) -> None:
    hm.HistoricalCustomUser.objects.filter(instance_id=str(user_id)).delete()
    hm.HistoricalPaymentCardAccount.objects.filter(instance_id__in=[str(val) for val in pcards_ids]).delete()
    hm.HistoricalSchemeAccount.objects.filter(instance_id__in=[str(val) for val in mcards_ids]).delete()
    hm.HistoricalPaymentCardAccountEntry.objects.filter(
        user_id=user_id, payment_card_account_id__in=pcards_ids
    ).delete()
    hm.HistoricalSchemeAccountEntry.objects.filter(user_id=user_id, scheme_account_id__in=mcards_ids).delete()
    hm.HistoricalPaymentCardSchemeEntry.objects.filter(
        payment_card_account_id__in=pcards_ids, scheme_account_id__in=mcards_ids
    ).delete()


def _right_to_be_forgotten(user_id: str, entry_id: int) -> tuple[bool, str]:
    try:
        user = CustomUser.objects.prefetch_related(
            "plluserassociation_set", "scheme_account_set", "paymentcardaccountentry_set"
        ).get(id=int(user_id))
    except CustomUser.DoesNotExist:
        return False, "User not found"
    except ValueError:
        return False, "Invalid User ID"

    try:
        with transaction.atomic():
            _forget_user(user)
            vop_deactivation_map = _forget_plls(user)
            forgotten_mcards_ids = _forget_membership_cards(user)
            forgotten_pcards = _forget_payment_cards(user)
            _forget_history(user.id, [pcard.id for pcard in forgotten_pcards], forgotten_mcards_ids)

    except Exception as e:
        return False, repr(e)

    # send requests to metis only if db changes committed successfully
    for pcard in forgotten_pcards:
        activations = vop_deactivation_map.get(pcard.id, None)
        delete_and_redact_payment_card(
            pcard,
            activations=activations,
            priority=4,
            x_azure_ref=f"Triggered by django admin FileScript of id {entry_id}",
        )

    return True, ""
