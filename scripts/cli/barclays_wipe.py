from contextlib import contextmanager
from typing import TYPE_CHECKING

from django.db import connection
from django.db.models import IntegerField, ProtectedError, signals
from django.db.models.functions import Cast

from history import models as hm
from history.enums import HistoryModel
from history.signals import signal_record_history
from payment_card.models import PaymentCardAccount
from scheme.models import SchemeAccount
from ubiquity.models import PaymentCardSchemeEntry, VopActivation, update_pll_links_on_delete
from user.models import ClientApplicationBundle, CustomUser

if TYPE_CHECKING:
    from django.core.management.base import OutputWrapper


BARCLAYS_CHANNEL = "com.barclays.bmb"


def _handle_cascade(stdout: "OutputWrapper", msg: str, deleted_items: dict):
    if deleted_items:
        msg += (
            ", as result "
            + " and ".join([f"{v} {k.rsplit('.',1)[1]}" for k, v in deleted_items.items()])
            + " have been cascade deleted as well"
        )

    stdout.write(msg)


def _collects_ids_from_history_tables() -> tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]:
    users_ids: tuple[int, ...] = tuple(
        hm.HistoricalCustomUser.objects.values_list(Cast("instance_id", output_field=IntegerField()), flat=True)
        .filter(channel=BARCLAYS_CHANNEL)
        .distinct()
        .all()
    )

    return (
        users_ids,
        tuple(
            hm.HistoricalPaymentCardAccountEntry.objects.values_list("payment_card_account_id", flat=True)
            .filter(user_id__in=users_ids)
            .distinct()
            .all()
        ),
        tuple(
            hm.HistoricalSchemeAccountEntry.objects.values_list("scheme_account_id", flat=True)
            .filter(user_id__in=users_ids)
            .distinct()
            .all()
        ),
    )


@contextmanager
def disabled_delete_signals() -> None:
    for sender in HistoryModel:
        signals.pre_delete.disconnect(
            signal_record_history, sender=sender.value, dispatch_uid=f"{sender.value}_pre_delete"
        )
    signals.post_delete.disconnect(update_pll_links_on_delete, PaymentCardSchemeEntry)
    yield
    for sender in HistoryModel:
        signals.pre_delete.connect(
            signal_record_history, sender=sender.value, dispatch_uid=f"{sender.value}_pre_delete"
        )
    signals.post_delete.connect(update_pll_links_on_delete, PaymentCardSchemeEntry)


def _hard_delete_soft_deleted_items(
    stdout: "OutputWrapper",
    *,
    users_ids: tuple[int, ...],
    payment_cards_ids: tuple[int, ...],
    scheme_accounts_ids: tuple[int, ...],
) -> None:
    with disabled_delete_signals():
        deleted_n, deleted_items = CustomUser.all_objects.filter(id__in=users_ids).delete()
        msg = f"* deleted {deleted_n} CustomUsers"
        deleted_items.pop("user.CustomUser", None)
        _handle_cascade(stdout, msg, deleted_items)
        deleted_n, _ = VopActivation.objects.filter(payment_card_account_id__in=payment_cards_ids).delete()
        stdout.write(f"* deleted {deleted_n} VopActivations")
        deleted_n, deleted_items = PaymentCardAccount.all_objects.filter(
            id__in=payment_cards_ids, is_deleted=True
        ).delete()
        msg = f"* deleted {deleted_n} PaymentCardAccounts"
        deleted_items.pop("payment_card.PaymentCardAccount", None)
        _handle_cascade(stdout, msg, deleted_items)
        deleted_n, deleted_items = SchemeAccount.all_objects.filter(
            id__in=scheme_accounts_ids, is_deleted=True
        ).delete()
        msg = f"* deleted {deleted_n} SchemeAccounts"
        deleted_items.pop("scheme.SchemeAccount", None)
        _handle_cascade(stdout, msg, deleted_items)
        if payment_cards_ids:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM periodic_retry_periodicretry pr "
                    "WHERE (pr.\"data\"->'context'->>'card_id')::int IN %s;",
                    [payment_cards_ids],
                )
                deleted_n = cursor.rowcount
        else:
            deleted_n = 0
        stdout.write(f"* deleted {deleted_n} PeriodicRetries")


def _delete_org_data(stdout: "OutputWrapper") -> None:
    try:
        bundle = ClientApplicationBundle.objects.select_related("client__organisation").get(bundle_id=BARCLAYS_CHANNEL)
    except ClientApplicationBundle.DoesNotExist:
        stdout.write("* Barclays' ClientApplicationBundle not found, skipping...")
        return

    client = bundle.client
    organisation = client.organisation

    _, deleted_items = bundle.delete()
    msg = "* deleted Barclays' ClientApplicationBundle"
    deleted_items.pop("user.ClientApplicationBundle", None)
    _handle_cascade(stdout, msg, deleted_items)

    try:
        client.delete()
    except ProtectedError:
        with disabled_delete_signals():
            left_over_users, _ = CustomUser.all_objects.filter(client=client).delete()
        stdout.write(
            f"  * {left_over_users} CustomUsers that were not pickedup by the history tables have been deleted"
        )
        client.delete()

    stdout.write("* deleted Barcalys' ClientApplication")

    try:
        organisation.delete()
    except ProtectedError:
        stdout.write("* Barclays' Organisation was kept as another ClientApplication is using it")
    else:
        stdout.write("* deleted Barclays' Organisation")


def _delete_history(
    stdout: "OutputWrapper",
    *,
    users_ids: tuple[int, ...],
    payment_cards_ids: tuple[int, ...],
    scheme_accounts_ids: tuple[int, ...],
) -> None:
    # By payment_cards_ids
    if payment_cards_ids:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM history_historicalpaymentcardaccount hpca WHERE hpca.instance_id::int IN %s;",
                [payment_cards_ids],
            )
            n_deleted = cursor.rowcount
    else:
        n_deleted = 0

    stdout.write(f"* deleted {n_deleted} HistoricalPaymentCardAccounts")
    n_deleted, _ = hm.HistoricalPaymentCardSchemeEntry.objects.filter(
        payment_card_account_id__in=payment_cards_ids
    ).delete()
    stdout.write(f"* deleted {n_deleted} HistoricalPaymentCardSchemeEntry (by payment card id)")

    # By scheme_accounts_ids
    if scheme_accounts_ids:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM history_historicalschemeaccount hsa WHERE hsa.instance_id::int IN %s;",
                [scheme_accounts_ids],
            )
            n_deleted = cursor.rowcount
    else:
        n_deleted = 0
    stdout.write(f"* deleted {n_deleted} HistoricalSchemeAccount")
    n_deleted, _ = hm.HistoricalPaymentCardSchemeEntry.objects.filter(
        scheme_account_id__in=scheme_accounts_ids
    ).delete()
    stdout.write(f"* deleted {n_deleted} HistoricalPaymentCardSchemeEntry (by scheme account id)")

    # By users_ids
    n_deleted, _ = hm.HistoricalVopActivation.objects.filter(user_id__in=users_ids).delete()
    stdout.write(f"* deleted {n_deleted} HistoricalVopActivation")
    n_deleted, _ = hm.HistoricalPaymentCardAccountEntry.objects.filter(user_id__in=users_ids).delete()
    stdout.write(f"* deleted {n_deleted} HistoricalPaymentCardAccountEntry")
    n_deleted, _ = hm.HistoricalSchemeAccountEntry.objects.filter(user_id__in=users_ids).delete()
    stdout.write(f"* deleted {n_deleted} HistoricalSchemeAccountEntry")
    if users_ids:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM history_historicalcustomuser hcu WHERE hcu.instance_id::int IN %s;",
                [users_ids],
            )
            n_deleted = cursor.rowcount
    else:
        n_deleted = 0

    stdout.write(f"* deleted {n_deleted} HistoricalCustomUser")


def wipe_barclays_data(*, stdout: "OutputWrapper") -> str:
    # STEP 1 - collect users, payment and membership cards
    stdout.write("Collecting Users IDs, Scheme Account IDs, and Payment Card Accounts IDs from Hisory tables...")
    users_ids, payment_cards_ids, scheme_accounts_ids = _collects_ids_from_history_tables()
    stdout.write(
        f"Collected {len(users_ids)} users ids, {len(payment_cards_ids)} "
        f"payment card accounts ids, and {len(scheme_accounts_ids)} scheme accounts ids."
    )

    # STEP 2 - left over data
    stdout.write("Hard deleting soft deleted Barclays data.")
    _hard_delete_soft_deleted_items(
        stdout, users_ids=users_ids, payment_cards_ids=payment_cards_ids, scheme_accounts_ids=scheme_accounts_ids
    )
    stdout.write("Deleting Barclays' Organisation, ClientApplication, and ClientApplicationBundle")
    _delete_org_data(stdout)

    # STEP 3 - delete history
    stdout.write("Deleting Barclays data from History tables")
    _delete_history(
        stdout, users_ids=users_ids, payment_cards_ids=payment_cards_ids, scheme_accounts_ids=scheme_accounts_ids
    )
    stdout.write("History tables cleaned successfully.")
