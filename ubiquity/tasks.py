import logging
import math
import typing as t
from enum import Enum

import arrow
import requests
import sentry_sdk
from celery import shared_task
from django.conf import settings
from django.db.models import Q
from rest_framework import serializers

from api_messaging.midas_messaging import send_midas_last_loyalty_card_removed
from hermes.vop_tasks import activate, deactivate
from history.data_warehouse import (
    generate_pll_delete_payload,
    remove_loyalty_card_event,
    to_data_warehouse,
    user_pll_delete_event,
)
from history.tasks import auth_outcome_task
from history.utils import clean_history_kwargs, history_bulk_update, set_history_kwargs, user_info
from payment_card import metis
from payment_card.models import PaymentCardAccount
from scheme.mixins import BaseLinkMixin, SchemeAccountJoinMixin
from scheme.models import SchemeAccount
from scheme.serializers import LinkSchemeSerializer
from ubiquity.models import (
    AccountLinkStatus,
    PaymentCardSchemeEntry,
    PllUserAssociation,
    SchemeAccountEntry,
    VopActivation,
)
from user.models import ClientApplicationBundle, CustomUser

if t.TYPE_CHECKING:
    from rest_framework.serializers import Serializer

logger = logging.getLogger(__name__)


class UpdateCardType(Enum):
    PAYMENT_CARD = PaymentCardAccount
    MEMBERSHIP_CARD = SchemeAccount


# Call back retry tasks for activation and deactivation - called from background
def retry_activation(data):
    retry_obj = data["periodic_retry_obj"]
    activation = VopActivation.objects.get(id=data["context"]["activation_id"])
    status, result = activate(activation, data["context"]["post_data"])
    retry_obj.status = status
    retry_obj.results += [result]


def retry_deactivation(data):
    retry_obj = data["periodic_retry_obj"]
    activation = VopActivation.objects.get(id=data["context"]["activation_id"])
    status, result = deactivate(activation, data["context"]["post_data"])
    retry_obj.status = status
    retry_obj.results += [result]


def _send_metrics_to_atlas(method: str, slug: str, payload: dict, x_azure_ref: str | None = None) -> None:
    headers = {
        "Authorization": f"Token {settings.SERVICE_API_KEY}",
        "Content-Type": "application/json",
        "X-azure-ref": x_azure_ref,
    }
    requests.request(method, f"{settings.ATLAS_URL}/audit/metrics/{slug}", data=payload, headers=headers)


@shared_task
def async_link(
    auth_fields: dict,
    scheme_account_id: int,
    user_id: int,
    payment_cards_to_link: list,
    history_kwargs: dict | None = None,
    headers: dict | None = None,
) -> None:
    set_history_kwargs(history_kwargs)

    scheme_account = SchemeAccount.objects.select_related("scheme").get(id=scheme_account_id)
    user = CustomUser.objects.get(id=user_id)
    scheme_account_entry = SchemeAccountEntry.objects.get(user=user, scheme_account=scheme_account)
    try:
        serializer = LinkSchemeSerializer(data=auth_fields, context={"scheme_account_entry": scheme_account_entry})
        if payment_cards_to_link:
            PllUserAssociation.link_user_scheme_account_to_payment_cards(
                scheme_account, payment_cards_to_link, user, headers
            )
            # auto_link_membership_to_payments(payment_cards_to_link, scheme_account)
        BaseLinkMixin.link_account(serializer, scheme_account, user, scheme_account_entry, headers)
        clean_history_kwargs(history_kwargs)

    except serializers.ValidationError as e:
        scheme_account_entry.set_link_status(AccountLinkStatus.INVALID_CREDENTIALS)
        # scheme_account.status = scheme_account.INVALID_CREDENTIALS
        scheme_account.save()
        clean_history_kwargs(history_kwargs)
        raise e


@shared_task
def async_balance(scheme_account_entry: "SchemeAccountEntry", delete_balance=False, headers: dict | None = None) -> None:
    if delete_balance:
        scheme_account_entry.scheme_account.delete_cached_balance()
        scheme_account_entry.scheme_account.delete_saved_balance()

    scheme_account_entry.scheme_account.get_balance(scheme_account_entry, headers)


@shared_task
def async_balance_with_updated_credentials(
    instance_id: int,
    scheme_account_entry: SchemeAccountEntry,
    payment_cards_to_link: list,
    relink_pll: bool = False,
    send_auth_outcome: bool = False,
) -> None:
    scheme_account = SchemeAccount.objects.get(id=instance_id)
    scheme_account.delete_cached_balance()
    scheme_account.delete_saved_balance()

    logger.debug(f"Attempting to get balance with updated credentials for SchemeAccount (id={scheme_account.id})")
    balance, _ = scheme_account.get_balance(scheme_account_entry=scheme_account_entry)

    if balance:
        logger.debug(
            "Balance returned from balance call with updated credentials - SchemeAccount (id={scheme_account.id}) - "
            "Updating credentials."
        )

        scheme_account_entry.set_link_status(AccountLinkStatus.ACTIVE)
        if send_auth_outcome:
            auth_outcome_task(success=True, scheme_account_entry=scheme_account_entry)

        if relink_pll and payment_cards_to_link:
            PllUserAssociation.link_users_payment_cards(scheme_account_entry, payment_cards_to_link)
    else:
        logger.debug(
            f"No balance returned from balance call with updated credentials - SchemeAccount (id={scheme_account.id}) -"
            " Unauthorising user."
        )

        if send_auth_outcome:
            auth_outcome_task(success=False, scheme_account_entry=scheme_account_entry)
        scheme_account_entry.set_link_status(AccountLinkStatus.INVALID_CREDENTIALS)


@shared_task
def async_all_balance(user_id: int, channels_permit, headers: dict | None = None) -> None:
    query = {"user": user_id, "scheme_account__is_deleted": False}
    exclude_query = {"link_status__in": AccountLinkStatus.exclude_balance_statuses()}
    entries = channels_permit.related_model_query(
        SchemeAccountEntry.objects.filter(**query), "scheme_account__scheme__"
    )

    # If the channel is trusted we shouldn't make calls to the merchant to refresh balance,
    # since the user would have no stored auth credentials.
    is_trusted_channel = ClientApplicationBundle.objects.values_list("is_trusted", flat=True).get(
        bundle_id=channels_permit.bundle_id
    )
    if not is_trusted_channel:
        entries = entries.exclude(**exclude_query)

        for entry in entries.all():
            async_balance.delay(entry, headers=headers)


@shared_task
def async_join(
    scheme_account_id: int,
    user_id: int,
    serializer: "Serializer",
    scheme_id: int,
    validated_data: dict,
    channel: str,
    payment_cards_to_link: list,
    history_kwargs: dict | None = None,
    headers: dict | None = None,
) -> None:
    set_history_kwargs(history_kwargs)

    user = CustomUser.objects.get(id=user_id)
    scheme_account = SchemeAccount.objects.get(id=scheme_account_id)

    if payment_cards_to_link:
        PllUserAssociation.link_user_scheme_account_to_payment_cards(
            scheme_account, payment_cards_to_link, user, headers
        )
        # auto_link_membership_to_payments(payment_cards_to_link, scheme_account)

    SchemeAccountJoinMixin().handle_join_request(
        validated_data, user, scheme_id, scheme_account, serializer, channel, headers
    )

    clean_history_kwargs(history_kwargs)


@shared_task
def async_registration(
    user_id: int,
    serializer: "Serializer",
    scheme_account_id: int,
    validated_data: dict,
    channel: str,
    history_kwargs: dict | None = None,
    delete_balance=False,
    headers: dict | None = None,
) -> None:
    set_history_kwargs(history_kwargs)
    user = CustomUser.objects.get(id=user_id)
    scheme_account = SchemeAccount.objects.get(id=scheme_account_id)
    if delete_balance:
        scheme_account.delete_cached_balance()
        scheme_account.delete_saved_balance()

    SchemeAccountJoinMixin().handle_join_request(
        validated_data, user, scheme_account.scheme_id, scheme_account, serializer, channel, headers
    )

    clean_history_kwargs(history_kwargs)


@shared_task
def async_join_journey_fetch_balance_and_update_status(
    scheme_account_id: int, scheme_account_entry_id: int, headers: dict | None = None
) -> None:
    # After successful join, keep scheme account entry as pending until we have fetched balance
    # Pending used rather than join pending to not re-trigger this logic
    scheme_account = SchemeAccount.objects.get(id=scheme_account_id)
    scheme_account_entry = SchemeAccountEntry.objects.get(id=scheme_account_entry_id)
    scheme_account_entry.set_link_status(AccountLinkStatus.PENDING)
    scheme_account.get_balance(scheme_account_entry, headers)


def _format_info(scheme_account: SchemeAccount, user_id: int) -> dict:
    consents = scheme_account.userconsent_set.filter(user_id=user_id).all()
    return {
        "card_number": scheme_account.card_number,
        "link_date": scheme_account.link_date,
        "consents": [{"text": c.metadata["text"], "answer": c.value} for c in consents],
    }


@shared_task
def send_merchant_metrics_for_new_account(user_id: int, scheme_account_id: int, scheme_slug: str) -> None:
    scheme_account = SchemeAccount.objects.get(pk=scheme_account_id)
    consents = scheme_account.userconsent_set.filter(user_id=user_id).all()
    payload = {
        "scheme_account_id": scheme_account_id,
        "card_number": scheme_account.card_number,
        "link_date": scheme_account.link_date,
        "consents": [{"text": c.metadata["text"], "answer": c.value} for c in consents],
    }
    if not payload["link_date"]:
        del payload["link_date"]

    _send_metrics_to_atlas("POST", scheme_slug, payload)


@shared_task
def send_merchant_metrics_for_link_delete(
    scheme_account_id: int, scheme_slug: str, date: str, date_type: str, headers: dict | None = None
) -> None:
    if date_type not in ("link", "delete"):
        raise ValueError(f"{date_type} in an invalid merchant metrics date_type")

    payload = {"scheme_account_id": scheme_account_id, f"{date_type}_date": date}
    _send_metrics_to_atlas("PATCH", scheme_slug, payload, headers.get("X-azure-ref", None) if headers else None)


@shared_task
def deleted_payment_card_cleanup(
    payment_card_id: t.Optional[int],
    payment_card_hash: t.Optional[str],
    user_id: int,
    history_kwargs: dict | None = None,
    headers: dict | None = None,
) -> None:
    set_history_kwargs(history_kwargs)
    if payment_card_id is not None:
        query = {"pk": payment_card_id}
    else:
        query = {"hash": payment_card_hash}

    payment_card_account = PaymentCardAccount.objects.prefetch_related("paymentcardschemeentry_set").get(**query)
    p_card_users = payment_card_account.user_set.values_list("id", flat=True).all()
    pll_links = payment_card_account.paymentcardschemeentry_set.all()

    user_plls = PllUserAssociation.objects.filter(pll__in=pll_links, user__id=user_id)

    # Generate event payload for pll_link.status_change
    delete_user_pll_payloads = generate_pll_delete_payload(user_plls)

    user_plls.delete()

    user_pll_delete_event(delete_user_pll_payloads, headers)

    if not p_card_users:
        payment_card_account.is_deleted = True
        payment_card_account.save(update_fields=["is_deleted"])
        metis.delete_payment_card(payment_card_account, run_async=False, headers=headers)

    else:
        pll_links = pll_links.exclude(scheme_account__user_set__id__in=p_card_users)

    # deleted_link_ids = [link.id for link in pll_links]
    # Pll links delete triggers the delete signal on the base link which also removes PllUserAssociations and
    # recomputes the user link status and slug. Could be made more efficient as this is done on every link
    pll_links.delete()

    # @todo pll stuff removed this if ok - pll_links
    # Updates any ubiquity collisions linked to this payment card
    # for entry in payment_card_account.paymentcardschemeentry_set.exclude(id__in=deleted_link_ids).all():
    #    entry.update_soft_links({"payment_card_account": payment_card_account})

    clean_history_kwargs(history_kwargs)


@shared_task
def deleted_membership_card_cleanup(
    scheme_account_entry: SchemeAccountEntry, delete_date: str, history_kwargs: dict | None = None, headers: dict | None = None
) -> None:
    set_history_kwargs(history_kwargs)
    scheme_slug = scheme_account_entry.scheme_account.scheme.slug
    user = scheme_account_entry.user

    # todo: review PLL behaviour on card deletion in P3
    pll_links = PaymentCardSchemeEntry.objects.filter(
        scheme_account_id=scheme_account_entry.scheme_account.id
    ).prefetch_related("scheme_account", "payment_card_account", "payment_card_account__paymentcardschemeentry_set")

    remove_loyalty_card_event(scheme_account_entry, date_time=delete_date, headers=headers)

    # @todo consider if the next line is redundant - deleting base_pll cascades delete PLLAssociation on foreign key
    #  also pll_links.delete() does this with a post delete signal.

    user_plls = PllUserAssociation.objects.filter(pll__in=pll_links, user=user)

    # Generate payload for event pll_link.statuschange
    delete_user_pll_payloads = generate_pll_delete_payload(user_plls)

    user_plls.delete()
    user_pll_delete_event(delete_user_pll_payloads, headers)

    other_scheme_account_entries = SchemeAccountEntry.objects.filter(
        scheme_account=scheme_account_entry.scheme_account
    ).exclude(id=scheme_account_entry.id)

    if other_scheme_account_entries.count() <= 0:
        # Last man standing
        send_midas_last_loyalty_card_removed(scheme_account_entry)
        scheme_account_entry.scheme_account.is_deleted = True
        scheme_account_entry.scheme_account.save(update_fields=["is_deleted"])

    else:
        # todo: Some PLL link nonsense to look at here for Phase 3 - This should work ok
        m_card_users = other_scheme_account_entries.values_list("user_id", flat=True)
        pll_links = pll_links.exclude(payment_card_account__user_set__in=m_card_users)

    # Delete this user's scheme account entry (credentials and PLLUserAssociations by cascade)
    scheme_account_entry.delete()

    activations = VopActivation.find_activations_matching_links(pll_links)

    # related_pcards = {link.payment_card_account for link in pll_links}
    # deleted_pll_link_ids = {link.id for link in pll_links}

    # Pll links delete triggers the delete signal on the base link which also removes PllUserAssociations and
    # recomputes the user link status and slug. Could be made more efficient as this is done on every link
    pll_links.delete()

    # @todo pll stuff removed this if ok - pll_links.delete() handles this now
    # Resolve ubiquity collisions for any PLL links related to the linked payment card accounts
    # for pcard in related_pcards:
    #    pcard_links = pcard.paymentcardschemeentry_set.exclude(id__in=deleted_pll_link_ids).all()
    #    for pcard_link in pcard_links:
    #       pcard_link.update_soft_links({"payment_card_account": pcard_link.payment_card_account_id})

    if scheme_slug in settings.SCHEMES_COLLECTING_METRICS:
        send_merchant_metrics_for_link_delete.delay(
            scheme_account_entry.scheme_account.id, scheme_slug, delete_date, "delete"
        )

    PaymentCardSchemeEntry.deactivate_activations(activations)
    clean_history_kwargs(history_kwargs)


@shared_task
def bulk_deleted_membership_card_cleanup(
    channel: str,
    bundle_id: int,
    scheme_id: int,
) -> None:
    logger.info("Starting cleanup for scheme account deletions")

    # could use user__client=bundle.client since users are shared across bundles for a single client
    # but this is more explicit
    scheme_acc_entries = SchemeAccountEntry.objects.filter(
        user__client__clientapplicationbundle=bundle_id, scheme_account__scheme=scheme_id
    )

    scheme_acc_and_user_ids = {(entry.scheme_account_id, entry.user_id) for entry in scheme_acc_entries}
    entry_count = len(scheme_acc_entries)

    set_history_kwargs({"table_user_id_column": "user_id"})
    scheme_acc_entries.delete()

    logger.debug(f"Deleted {entry_count} SchemeAccountEntrys as part of delete " "SchemeBundleAssociation cleanup...")

    accounts_to_clean_up_count = len(scheme_acc_and_user_ids)
    for index, scheme_acc_and_user_id in enumerate(scheme_acc_and_user_ids):
        scheme_acc_id, user_id = scheme_acc_and_user_id

        # Log at percentage-based intervals, so we don't spam logs for larger cleanups (minimum of 10)
        log_interval = max([10, math.ceil(accounts_to_clean_up_count / 100) * 20])
        if index > 0 and index % log_interval == 0:
            logger.debug(f"Triggered cleanup tasks for {index} scheme account deletions")

        deleted_membership_card_cleanup.delay(
            scheme_acc_id,
            arrow.utcnow().format(),
            user_id,
            history_kwargs={"user_info": user_info(user_id=user_id, channel=channel)},
        )

    logger.debug(
        "Scheme account deletion cleanup process executed - "
        f"Total scheme account cleanup tasks executed: {accounts_to_clean_up_count}"
    )


def _send_data_to_atlas(consent: dict, x_azure_ref: str | None = None) -> None:
    url = f"{settings.ATLAS_URL}/audit/ubiquity_user/save"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Token {}".format(settings.SERVICE_API_KEY),
        "X-azure-ref": x_azure_ref,
    }
    data = {
        "email": consent["email"],
        "ubiquity_join_date": arrow.get(consent["timestamp"]).format("YYYY-MM-DD hh:mm:ss"),
    }
    requests.post(url=url, headers=headers, json=data)


def _delete_user_membership_cards(
    user: "CustomUser", m_cards: list[SchemeAccount], send_deactivation: bool = True, headers: dict | None = None
) -> None:
    cards_to_delete = []
    for card in m_cards:
        if card.user_set.count() == 1:
            card.is_deleted = True
            cards_to_delete.append(card)

    user_card_entries = user.schemeaccountentry_set.all()

    for user_card_entry in user_card_entries:
        remove_loyalty_card_event(user_card_entry, headers)

    # VOP deactivate
    links_to_remove = PaymentCardSchemeEntry.objects.filter(scheme_account__in=cards_to_delete)
    if send_deactivation:
        vop_links = links_to_remove.filter(payment_card_account__payment_card__slug="visa")
        activations = VopActivation.find_activations_matching_links(vop_links)
        PaymentCardSchemeEntry.deactivate_activations(activations, headers)

    links_to_remove.delete()
    history_bulk_update(SchemeAccount, cards_to_delete, ["is_deleted"])
    user_card_entries.delete()


def _delete_user_payment_cards(
    user: "CustomUser", p_cards: list[PaymentCardAccount], run_async: bool = True, headers: dict | None = None
) -> None:
    cards_to_delete = []
    for card in p_cards:
        if card.user_set.count() == 1:
            card.is_deleted = True
            cards_to_delete.append(card)
            metis.delete_payment_card(card, run_async=run_async, headers=headers)
        else:
            # Updates any ubiquity collisions linked to this payment card
            for entry in card.paymentcardschemeentry_set.all():
                PllUserAssociation.update_user_pll_by_both(entry.payment_card_account, entry.scheme_account)

    PaymentCardSchemeEntry.objects.filter(payment_card_account_id__in=[card.id for card in cards_to_delete]).delete()

    user_card_entries = user.paymentcardaccountentry_set.all()

    for user_card_entry in user_card_entries:
        pay_card = user_card_entry.payment_card_account
        cabs = user.client.clientapplicationbundle_set.all()
        for cab in cabs:
            payload = {
                "event_type": "payment.account.removed",
                "origin": "channel",
                "channel": cab.bundle_id,
                "event_date_time": arrow.utcnow().isoformat(),
                "external_user_ref": user.external_id,
                "internal_user_ref": user.id,
                "email": user.email,
                "payment_account_id": pay_card.id,
                "fingerprint": pay_card.fingerprint,
                "expiry_date": f"{pay_card.expiry_month}/{pay_card.expiry_year}",
                "token": pay_card.token,
                "status": pay_card.status,
            }
            to_data_warehouse(payload, headers)

        history_bulk_update(PaymentCardAccount, cards_to_delete, ["is_deleted"])
        user_card_entry.delete()


@shared_task
def deleted_service_cleanup(user_id: int, consent: dict, history_kwargs: dict | None = None, headers: dict | None = None) -> None:
    set_history_kwargs(history_kwargs)
    user = CustomUser.all_objects.get(id=user_id)
    # A user should always have a consent in normal circumstances but this is just in case one doesn't so
    # the rest of the cleanup is still completed.
    if hasattr(user, "serviceconsent"):
        user.serviceconsent.delete()

    m_cards = user.scheme_account_set.prefetch_related("user_set").all()
    p_cards = user.payment_card_account_set.prefetch_related("user_set", "paymentcardschemeentry_set").all()

    user_plls = PllUserAssociation.objects.filter(
        Q(user__id=user.id), Q(pll__scheme_account_id__in=m_cards) | Q(pll__payment_card_account_id__in=p_cards)
    )

    # Generate payload for event pll_link.statuschange
    delete_user_pll_payloads = generate_pll_delete_payload(user_plls)

    user_plls.delete()

    # user pll event
    user_pll_delete_event(delete_user_pll_payloads, headers)

    # Don't deactivate when removing membership card as it will race with delete payment card
    # Deleting all payment cards causes an un-enrol for each card which also deactivates all linked activations
    # if a payment card was linked to 2 accounts its activations will not be deleted
    _delete_user_membership_cards(user, m_cards, send_deactivation=False, headers=headers)
    _delete_user_payment_cards(user, p_cards, run_async=False, headers=headers)
    clean_history_kwargs(history_kwargs)

    try:  # send user info to be persisted in Atlas
        _send_data_to_atlas(consent, headers.get("X-azure-ref", None) if headers else None)
    except Exception:
        sentry_sdk.capture_exception()


def _update_one_card_with_many_new_pll_links(
    card_to_update: t.Union[PaymentCardAccount, SchemeAccount], new_links_ids: list
) -> None:
    card_to_update.refresh_from_db(fields=["pll_links"])
    existing_links = [link["id"] for link in card_to_update.pll_links]
    card_to_update.pll_links.extend(
        [{"id": card_id, "active_link": True} for card_id in new_links_ids if card_id not in existing_links]
    )
    card_to_update.save(update_fields=["pll_links"])


def _update_many_cards_with_one_new_pll_link(
    card_model: UpdateCardType,
    cards_to_update_ids: list,
    new_link_id: int,
) -> None:
    updated_cards = []
    for card in card_model.value.objects.filter(id__in=cards_to_update_ids).all():
        if new_link_id not in [link["id"] for link in card.pll_links]:
            card.pll_links.append({"id": new_link_id, "active_link": True})
            updated_cards.append(card)

    card_model.value.objects.bulk_update(updated_cards, ["pll_links"])


def _process_vop_activations(created_links, prechecked=False):
    for link in created_links:
        link.vop_activate_check(prechecked=prechecked)


# @todo PLL stuff check that PllUserAssociation functions log history and events properly.

"""
This task has been removed and all instances replaced with PllUserAssociation function
The calls are from other tasks so no task instance was required.

@shared_task
def auto_link_membership_to_payments(
    payment_cards_to_link: list, membership_card: t.Union[SchemeAccount, int], history_kwargs: dict | None = None
) -> None:
    set_history_kwargs(history_kwargs)

    if isinstance(membership_card, int):
        membership_card = SchemeAccount.objects.get(id=membership_card)

    # the next two queries are meant to prevent more than one join and to avoid lookups with too many results.
    # they are executed as a single complex query by django.
    excluded_payment_cards = PaymentCardSchemeEntry.objects.filter(
        payment_card_account_id__in=payment_cards_to_link,
        scheme_account__is_deleted=False,
        scheme_account__scheme_id=membership_card.scheme_id,
    ).values_list("payment_card_account_id", flat=True)

    payment_cards_to_link = (
        PaymentCardAccount.all_objects.filter(id__in=payment_cards_to_link, is_deleted=False)
        .select_related("payment_card")
        .all()
    )

    link_entries_to_create = []
    pll_activated_payment_cards = []
    vop_activated_cards = []
    for payment_card_account in payment_cards_to_link:
        if payment_card_account.id in excluded_payment_cards:
            # todo: PLL stuff
            entry = PaymentCardSchemeEntry(
                scheme_account=membership_card,
                payment_card_account=payment_card_account,
                slug=PaymentCardSchemeEntry.UBIQUITY_COLLISION,
            ).get_instance_with_active_status()
        else:
            # todo: PLL stuff
            entry = PaymentCardSchemeEntry(
                scheme_account=membership_card, payment_card_account=payment_card_account
            ).get_instance_with_active_status()

        link_entries_to_create.append(entry)
        if entry.active_link:
            pll_activated_payment_cards.append(payment_card_account.id)
            if payment_card_account.payment_card.slug == PaymentCard.VISA:
                vop_activated_cards.append(payment_card_account.id)

    created_links = history_bulk_create(
        PaymentCardSchemeEntry, link_entries_to_create, batch_size=100, ignore_conflicts=True
    )

    logger.info(
        "auto-linked SchemeAccount %s to PaymentCardAccounts %s, of which %s were active links",
        membership_card.id,
        [card.id for card in payment_cards_to_link],
        len(pll_activated_payment_cards),
    )
    logger.debug("SchemeAccount %s status: %s", membership_card.id, membership_card.status)

    _update_one_card_with_many_new_pll_links(membership_card, pll_activated_payment_cards)
    _update_many_cards_with_one_new_pll_link(
        UpdateCardType.PAYMENT_CARD, pll_activated_payment_cards, membership_card.id
    )
    _process_vop_activations(
        [link for link in created_links if link.payment_card_account_id in vop_activated_cards], prechecked=True
    )
    clean_history_kwargs(history_kwargs)
"""

"""
def _get_instances_to_bulk_create(
    payment_card_account: PaymentCardAccount, wallet_scheme_account_entries: list, just_created: bool
) -> dict:

    if just_created:
        already_linked_scheme_ids = []
    else:
        already_linked_scheme_ids = PaymentCardSchemeEntry.objects.filter(
            payment_card_account=payment_card_account
        ).values_list("scheme_account__scheme_id", flat=True)

    cards_by_scheme_ids = {}
    instances_to_bulk_create = {}
    for scheme_account_entry in wallet_scheme_account_entries:
        scheme_account = scheme_account_entry.scheme_account
        scheme_id = scheme_account.scheme_id
        scheme_account_status = scheme_account_entry.link_status
        # @todo: PLL stuff none - reworked to use wallet_scheme_account_entries. A link is only created if
        # the scheme account does not share the same scheme as other cards in the wallet (ubiquity collision)
        # When this occurs only the latest card (highest id) is linked regardless of status
        # Note this is only done on a wallets membership cards it would work if the collision occurs across
        # wallets - We either live with this for API 1.0x or need to add across wallet Collision detection perhaps
        # setting status accordingly - may be run this extra collision check as a background task

        link = PaymentCardSchemeEntry(scheme_account=scheme_account, payment_card_account=payment_card_account)
        if scheme_id not in already_linked_scheme_ids:
            if scheme_id in cards_by_scheme_ids:
                if cards_by_scheme_ids[scheme_id] > scheme_account.id:
                    cards_by_scheme_ids[scheme_id] = scheme_account.id
                    # instances_to_bulk_create[scheme_id] = link.get_instance_with_active_status()
                    instances_to_bulk_create[scheme_id] = link.set_active_link_status(scheme_account_status)
            else:
                cards_by_scheme_ids[scheme_id] = scheme_account.id
                # instances_to_bulk_create[scheme_id] = link.get_instance_with_active_status()
                instances_to_bulk_create[scheme_id] = link.set_active_link_status(scheme_account_status)

    return instances_to_bulk_create
"""


@shared_task
def auto_link_payment_to_memberships(
    # wallet_scheme_account_entries: list,
    payment_card_account: t.Union[PaymentCardAccount, int],
    user_id: int,
    just_created: bool,
    history_kwargs: dict | None = None,
    headers: dict | None = None,
) -> None:
    set_history_kwargs(history_kwargs)

    if isinstance(payment_card_account, int):
        payment_card_account = PaymentCardAccount.objects.select_related("payment_card").get(pk=payment_card_account)

    if just_created:
        scheme_account_entries = SchemeAccountEntry.objects.filter(user=user_id).all()
        PllUserAssociation.link_users_scheme_accounts(payment_card_account, scheme_account_entries, headers)

    else:
        PllUserAssociation.update_user_pll_by_pay_account(payment_card_account, headers)

    """

    if isinstance(wallet_scheme_account_entries[0], int):
        wallet_scheme_account_entries = SchemeAccountEntry.objects.filter(id__in=wallet_scheme_account_entries).all()

    instances_to_bulk_create = _get_instances_to_bulk_create(
        payment_card_account, wallet_scheme_account_entries, just_created
    )
    pll_activated_membership_cards = [
        link.scheme_account_id for link in instances_to_bulk_create.values() if link.active_link is True
    ]

    created_links = history_bulk_create(
        PaymentCardSchemeEntry, instances_to_bulk_create.values(), batch_size=100, ignore_conflicts=True
    )

    _update_one_card_with_many_new_pll_links(payment_card_account, pll_activated_membership_cards)
    _update_many_cards_with_one_new_pll_link(
        UpdateCardType.MEMBERSHIP_CARD, pll_activated_membership_cards, payment_card_account.id
    )

    if payment_card_account.payment_card.slug == PaymentCard.VISA:
        _process_vop_activations(
            [link for link in created_links if link.scheme_account_id in pll_activated_membership_cards],
            prechecked=True,
        )
    """
    clean_history_kwargs(history_kwargs)
