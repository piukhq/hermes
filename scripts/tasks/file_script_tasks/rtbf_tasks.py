import hashlib
from typing import TYPE_CHECKING, cast
from uuid import uuid4

from celery import shared_task
from django.db import transaction
from django.db.models import Q

from hermes.utils import ctx
from history import models as hm
from history.data_warehouse import user_rtbf_event
from payment_card.metis import delete_and_redact_payment_card
from payment_card.models import PaymentCard, PaymentCardAccount
from scheme.models import SchemeAccount, SchemeAccountCredentialAnswer
from scripts.tasks.file_script_tasks import file_script_batch_task_base
from ubiquity.models import PaymentCardAccountEntry, PaymentCardSchemeEntry, SchemeAccountEntry
from ubiquity.utils import vop_deactivation_dict_by_payment_card_id
from user.models import CustomUser

if TYPE_CHECKING:
    from scripts.tasks.file_script_tasks import ResultType, ScriptRunnerType


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

        pll_to_delete.append(pll.id)
        if pll.active_link and pll.payment_card_account.payment_card_id == visa_payment_card_id:
            vop_deactivation_map[pll.payment_card_account_id] = vop_deactivation_dict_by_payment_card_id(
                pll.payment_card_account_id
            )

    user.plluserassociation_set.all().delete()
    PaymentCardSchemeEntry.objects.filter(id__in=pll_to_delete).delete()
    return vop_deactivation_map


def _forget_membership_cards(user: CustomUser) -> tuple[set[int], set[int]]:
    updated_mcards: list[SchemeAccount] = []
    ignored_mcards_ids: set[int] = set()
    links_to_delete: list[int] = []
    for mcard in cast(list[SchemeAccount], user.scheme_account_set.prefetch_related("schemeaccountentry_set").all()):
        links_to_delete.extend(mcard.schemeaccountentry_set.filter(user_id=user.id).values_list("id", flat=True).all())

        if mcard.schemeaccountentry_set.count() > 1:
            ignored_mcards_ids.add(mcard.id)
            # not last man standing. skip rest of logic.
            continue

        if mcard.alt_main_answer:
            mcard.alt_main_answer = _anonymised_value(mcard.alt_main_answer)

        mcard.is_deleted = True
        updated_mcards.append(mcard)

    if links_to_delete:
        SchemeAccountCredentialAnswer.objects.filter(scheme_account_entry_id__in=links_to_delete).delete()
        SchemeAccountEntry.objects.filter(id__in=links_to_delete).delete()

    if updated_mcards:
        SchemeAccount.all_objects.bulk_update(updated_mcards, fields=["is_deleted", "alt_main_answer"])

    return {card.id for card in updated_mcards}, ignored_mcards_ids


def _forget_payment_cards(user: CustomUser) -> tuple[list[PaymentCardAccount], set[int]]:
    updated_pcards: list[PaymentCardAccount] = []
    ignored_pcards_ids: set[int] = set()
    links_to_delete: list[int] = []

    for pcard in cast(
        list[PaymentCardAccount], user.payment_card_account_set.prefetch_related("paymentcardaccountentry_set").all()
    ):
        links_to_delete.extend(
            pcard.paymentcardaccountentry_set.filter(user_id=user.id).values_list("id", flat=True).all()
        )

        if pcard.paymentcardaccountentry_set.count() > 1:
            ignored_pcards_ids.add(pcard.id)

            # not last man standing. skip rest of logic.
            continue

        pcard.name_on_card = _anonymised_value(pcard.name_on_card)
        pcard.is_deleted = True
        updated_pcards.append(pcard)

    if links_to_delete:
        PaymentCardAccountEntry.objects.filter(id__in=links_to_delete).delete()

    if updated_pcards:
        PaymentCardAccount.all_objects.bulk_update(updated_pcards, fields=["is_deleted", "name_on_card"])

    return updated_pcards, ignored_pcards_ids


def _forget_history(
    user_id: int,
    pcards_ids: set[int],
    ignored_pcards_ids: set[int],
    mcards_ids: set[int],
    ignored_mcards_ids: set[int],
) -> list[PaymentCardAccount]:
    pcard_ids_to_delete: set[int] = set(
        hm.HistoricalPaymentCardAccountEntry.objects.filter(user_id=user_id)
        .exclude(payment_card_account_id__in=ignored_pcards_ids)
        .values_list("payment_card_account_id", flat=True)
        .all()
    )

    redact_only_updated_pcards: list[PaymentCardAccount] = []
    if history_only_pcard_ids := pcard_ids_to_delete - pcards_ids:
        for pcard in PaymentCardAccount.all_objects.filter(id__in=history_only_pcard_ids, is_deleted=True).all():
            pcard.name_on_card = _anonymised_value(pcard.name_on_card)
            redact_only_updated_pcards.append(pcard)

        if redact_only_updated_pcards:
            PaymentCardAccount.all_objects.bulk_update(redact_only_updated_pcards, fields=["name_on_card"])

    mcard_ids_to_delete: set[int] = set(
        hm.HistoricalSchemeAccountEntry.objects.filter(user_id=user_id)
        .exclude(scheme_account_id__in=ignored_mcards_ids)
        .values_list("scheme_account_id", flat=True)
        .all()
    )

    if history_only_mcard_ids := mcard_ids_to_delete - mcards_ids:
        updated_mcards: list[SchemeAccount] = []
        for mcard in SchemeAccount.all_objects.filter(id__in=history_only_mcard_ids, is_deleted=True).all():
            if mcard.alt_main_answer:
                mcard.alt_main_answer = _anonymised_value(mcard.alt_main_answer)
                updated_mcards.append(mcard)

        if updated_mcards:
            SchemeAccount.all_objects.bulk_update(updated_mcards, fields=["alt_main_answer"])

    hm.HistoricalCustomUser.objects.filter(instance_id=str(user_id)).delete()
    hm.HistoricalPaymentCardAccount.objects.filter(instance_id__in=[str(val) for val in pcard_ids_to_delete]).delete()
    hm.HistoricalSchemeAccount.objects.filter(instance_id__in=[str(val) for val in mcard_ids_to_delete]).delete()
    hm.HistoricalPaymentCardAccountEntry.objects.filter(user_id=user_id).delete()
    hm.HistoricalSchemeAccountEntry.objects.filter(user_id=user_id).delete()
    hm.HistoricalPaymentCardSchemeEntry.objects.filter(
        Q(
            payment_card_account_id__in=pcard_ids_to_delete,
            scheme_account_id__in=mcard_ids_to_delete | ignored_mcards_ids,
        )
        | Q(
            payment_card_account_id__in=pcard_ids_to_delete | ignored_pcards_ids,
            scheme_account_id__in=mcard_ids_to_delete,
        )
    ).delete()

    return redact_only_updated_pcards


def _right_to_be_forgotten(user_id: str, entry_id: int, script_runner: "ScriptRunnerType") -> tuple[bool, str]:
    ctx.x_azure_ref = f"Django Admin FileScript {entry_id}"

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
            forgotten_mcards_ids, ignored_mcards_ids = _forget_membership_cards(user)
            forgotten_pcards, ignored_pcards_ids = _forget_payment_cards(user)
            forgotten_pcards_ids = {pcard.id for pcard in forgotten_pcards}
            redact_only_pcards = _forget_history(
                user_id=user.id,
                pcards_ids=forgotten_pcards_ids,
                ignored_pcards_ids=ignored_pcards_ids,
                mcards_ids=forgotten_mcards_ids,
                ignored_mcards_ids=ignored_mcards_ids,
            )

    except Exception as e:
        return False, repr(e)

    # send requests to metis only if db changes committed successfully
    for pcard in forgotten_pcards:
        activations = vop_deactivation_map.get(pcard.id, None)
        delete_and_redact_payment_card(pcard, activations=activations, priority=4, x_azure_ref=ctx.x_azure_ref)

    for pcard in redact_only_pcards:
        delete_and_redact_payment_card(pcard, priority=1, redact_only=True, x_azure_ref=ctx.x_azure_ref)

    user_rtbf_event(
        user_id=user.id,
        scheme_accounts_ids=forgotten_mcards_ids,
        payment_accounts_ids=forgotten_pcards_ids,
        requesting_user_id=script_runner["pk"],
        requesting_user_email=script_runner["email"],
        headers={"X-azure-ref": ctx.x_azure_ref},
    )

    return True, ""


@shared_task
def right_to_be_forgotten_batch_task(ids: list[str], entry_id: int, script_runner: "ScriptRunnerType") -> "ResultType":
    return file_script_batch_task_base(ids, entry_id, script_runner, logic_fn=_right_to_be_forgotten)
