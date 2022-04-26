import logging
import typing as t
from datetime import datetime
from enum import Enum

import arrow
import requests
import sentry_sdk
from celery import shared_task
from django.conf import settings
from django.db.models import Q
from rest_framework import serializers
from rest_framework.exceptions import ParseError

import analytics
from hermes.vop_tasks import activate, deactivate
from history.data_warehouse import (
    add_and_auth_lc_event,
    register_lc_event,
    remove_loyalty_card_event,
    to_data_warehouse,
)
from history.utils import clean_history_kwargs, history_bulk_create, history_bulk_update, set_history_kwargs
from payment_card import metis
from payment_card.models import PaymentCard, PaymentCardAccount
from scheme.mixins import BaseLinkMixin, SchemeAccountJoinMixin, UpdateCredentialsMixin
from scheme.models import SchemeAccount
from scheme.serializers import LinkSchemeSerializer
from ubiquity.models import PaymentCardSchemeEntry, SchemeAccountEntry, VopActivation
from user.models import CustomUser

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


def _send_metrics_to_atlas(method: str, slug: str, payload: dict) -> None:
    headers = {"Authorization": f"Token {settings.SERVICE_API_KEY}", "Content-Type": "application/json"}
    requests.request(method, f"{settings.ATLAS_URL}/audit/metrics/{slug}", data=payload, headers=headers)


@shared_task
def async_link(
    auth_fields: dict, scheme_account_id: int, user_id: int, payment_cards_to_link: list, history_kwargs: dict = None
) -> None:
    set_history_kwargs(history_kwargs)

    scheme_account = SchemeAccount.objects.select_related("scheme").get(id=scheme_account_id)
    user = CustomUser.objects.get(id=user_id)
    try:
        serializer = LinkSchemeSerializer(data=auth_fields, context={"scheme_account": scheme_account})
        BaseLinkMixin.link_account(serializer, scheme_account, user)

        if payment_cards_to_link:
            auto_link_membership_to_payments(payment_cards_to_link, scheme_account)

        clean_history_kwargs(history_kwargs)

    except serializers.ValidationError as e:
        scheme_account.status = scheme_account.INVALID_CREDENTIALS
        scheme_account.save()
        clean_history_kwargs(history_kwargs)
        raise e


@shared_task
def async_balance(instance_id: int, delete_balance=False) -> None:
    scheme_account = SchemeAccount.objects.get(id=instance_id)
    if delete_balance:
        scheme_account.delete_cached_balance()
        scheme_account.delete_saved_balance()

    scheme_account.get_cached_balance()


@shared_task
def async_balance_with_updated_credentials(
    instance_id: int, user_id: int, update_fields: dict, scheme_questions
) -> None:
    scheme_account = SchemeAccount.objects.get(id=instance_id)
    scheme_account.delete_cached_balance()
    scheme_account.delete_saved_balance()
    cache_key = "scheme_{}".format(scheme_account.pk)

    # If updated credentials match existing credentials then update balance to change the status from pending
    # If a card was added with invalid credentials, the auth credentials are deleted and so may not exist.
    existing_answers = scheme_account.get_auth_credentials(force_all=True)
    if existing_answers:
        try:
            scheme_account.validate_auth_fields(update_fields, existing_answers)
            logger.debug(
                "Updated credentials match existing stored credentials. "
                f"Updating balance for SchemeAccount (id={scheme_account.id})"
            )
            scheme_account.update_cached_balance(cache_key=cache_key)
            return
        except ParseError:
            pass

    logger.debug(f"Attempting to get balance with updated credentials for SchemeAccount (id={scheme_account.id})")
    balance, _ = scheme_account.update_cached_balance(cache_key=cache_key, credentials_override=update_fields)

    if balance:
        logger.debug(
            "Balance returned from balance call with updated credentials - SchemeAccount (id={scheme_account.id}) - "
            "Updating credentials."
        )
        # update credentials and set all other linked users to unauthorised if they're different to the stored ones
        UpdateCredentialsMixin().update_credentials(scheme_account, update_fields, scheme_questions)

        SchemeAccountEntry.objects.filter(~Q(user_id=user_id), scheme_account=scheme_account).update(
            auth_provided=False
        )

        PaymentCardSchemeEntry.objects.filter(
            ~Q(payment_card_account__user_set=user_id), scheme_account=scheme_account
        ).delete()
    else:
        logger.debug(
            f"No balance returned from balance call with updated credentials - SchemeAccount (id={scheme_account.id}) -"
            " Unauthorising user."
        )
        mcard_entries = SchemeAccountEntry.objects.filter(scheme_account=scheme_account).all()
        for entry in mcard_entries:
            if entry.user_id == user_id:
                entry.auth_provided = False
                entry.save()
                break

        PaymentCardSchemeEntry.objects.filter(
            scheme_account=scheme_account, payment_card_account__user_set=user_id
        ).delete()

        if all(entry.auth_provided is False for entry in mcard_entries):
            scheme_account.schemeaccountcredentialanswer_set.filter(
                question__auth_field=True,
                question__manual_question=False,
            ).delete()
        else:
            # Call balance to correctly reset the scheme account balance using the stored credentials
            scheme_account.get_cached_balance()


@shared_task
def async_all_balance(user_id: int, channels_permit) -> None:
    query = {"user": user_id, "scheme_account__is_deleted": False}
    exclude_query = {"scheme_account__status__in": SchemeAccount.EXCLUDE_BALANCE_STATUSES}
    entries = channels_permit.related_model_query(
        SchemeAccountEntry.objects.filter(**query), "scheme_account__scheme__"
    )
    entries = entries.exclude(**exclude_query)

    for entry in entries:
        async_balance.delay(entry.scheme_account_id)


@shared_task
def async_join(
    scheme_account_id: int,
    user_id: int,
    serializer: "Serializer",
    scheme_id: int,
    validated_data: dict,
    channel: str,
    payment_cards_to_link: list,
    history_kwargs: dict = None,
) -> None:
    set_history_kwargs(history_kwargs)

    user = CustomUser.objects.get(id=user_id)
    scheme_account = SchemeAccount.objects.get(id=scheme_account_id)
    SchemeAccountJoinMixin().handle_join_request(validated_data, user, scheme_id, scheme_account, serializer, channel)

    if payment_cards_to_link:
        auto_link_membership_to_payments(payment_cards_to_link, scheme_account)

    clean_history_kwargs(history_kwargs)


@shared_task
def async_registration(
    user_id: int,
    serializer: "Serializer",
    scheme_account_id: int,
    validated_data: dict,
    channel: str,
    history_kwargs: dict = None,
    delete_balance=False,
) -> None:
    set_history_kwargs(history_kwargs)
    user = CustomUser.objects.get(id=user_id)
    scheme_account = SchemeAccount.objects.get(id=scheme_account_id)
    if delete_balance:
        scheme_account.delete_cached_balance()
        scheme_account.delete_saved_balance()

    SchemeAccountJoinMixin().handle_join_request(
        validated_data, user, scheme_account.scheme_id, scheme_account, serializer, channel
    )

    clean_history_kwargs(history_kwargs)

    # ~ check keys of validated_data to see if ONLY registratopn data supplied.....
    if "register_fields" in validated_data["consents"]:
        # send event to data warehouse
        register_lc_event(user, scheme_account)


@shared_task
def async_join_journey_fetch_balance_and_update_status(scheme_account_id: int) -> None:
    scheme_account = SchemeAccount.objects.get(id=scheme_account_id)
    scheme_account.status = scheme_account.PENDING
    scheme_account.save(update_fields=["status"])
    scheme_account.get_cached_balance()


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
def send_merchant_metrics_for_link_delete(scheme_account_id: int, scheme_slug: str, date: str, date_type: str) -> None:
    if date_type not in ("link", "delete"):
        raise ValueError(f"{date_type} in an invalid merchant metrics date_type")

    payload = {"scheme_account_id": scheme_account_id, f"{date_type}_date": date}
    _send_metrics_to_atlas("PATCH", scheme_slug, payload)


@shared_task
def deleted_payment_card_cleanup(
    payment_card_id: t.Optional[int], payment_card_hash: t.Optional[str], history_kwargs: dict = None
) -> None:
    set_history_kwargs(history_kwargs)
    if payment_card_id is not None:
        query = {"pk": payment_card_id}
    else:
        query = {"hash": payment_card_hash}

    payment_card_account = PaymentCardAccount.objects.get(**query)
    p_card_users = payment_card_account.user_set.values_list("id", flat=True).all()
    pll_links = PaymentCardSchemeEntry.objects.filter(payment_card_account_id=payment_card_account.id)

    if not p_card_users:
        payment_card_account.is_deleted = True
        payment_card_account.save(update_fields=["is_deleted"])
        metis.delete_payment_card(payment_card_account, run_async=False)

    else:
        pll_links = pll_links.exclude(scheme_account__user_set__id__in=p_card_users)

    pll_links.delete()
    clean_history_kwargs(history_kwargs)


@shared_task
def deleted_membership_card_cleanup(
    scheme_account_id: int, delete_date: str, user_id: int, history_kwargs: dict = None
) -> None:
    set_history_kwargs(history_kwargs)
    scheme_account = SchemeAccount.all_objects.get(id=scheme_account_id)
    user = CustomUser.objects.get(id=user_id)
    scheme_slug = scheme_account.scheme.slug

    pll_links = PaymentCardSchemeEntry.objects.filter(scheme_account_id=scheme_account.id).prefetch_related(
        "scheme_account"
    )
    entries_query = SchemeAccountEntry.objects.filter(scheme_account=scheme_account)

    remove_loyalty_card_event(user, scheme_account)

    if entries_query.count() <= 0:
        scheme_account.is_deleted = True
        scheme_account.save(update_fields=["is_deleted"])

        if user.client_id == settings.BINK_CLIENT_ID:
            analytics.update_scheme_account_attribute(
                scheme_account, user, old_status=dict(scheme_account.STATUSES).get(scheme_account.status_key)
            )

    else:
        remove_loyalty_card_event(user, scheme_account)

        user_mcard_auth_provided = entries_query.values_list("auth_provided", flat=True)
        if all((status is False for status in user_mcard_auth_provided)):
            scheme_account.status = SchemeAccount.WALLET_ONLY
            scheme_account.save(update_fields=["status"])
            PaymentCardSchemeEntry.update_active_link_status({"scheme_account": scheme_account})

            scheme_account.schemeaccountcredentialanswer_set.filter(
                question__auth_field=True,
                question__manual_question=False,
            ).delete()

        m_card_users = entries_query.values_list("user_id", flat=True)
        pll_links = pll_links.exclude(payment_card_account__user_set__in=m_card_users)

    activations = VopActivation.find_activations_matching_links(pll_links)
    pll_links.delete()

    if scheme_slug in settings.SCHEMES_COLLECTING_METRICS:
        send_merchant_metrics_for_link_delete.delay(scheme_account.id, scheme_slug, delete_date, "delete")

    PaymentCardSchemeEntry.deactivate_activations(activations)
    clean_history_kwargs(history_kwargs)


def _send_data_to_atlas(consent: dict) -> None:
    url = f"{settings.ATLAS_URL}/audit/ubiquity_user/save"
    headers = {"Content-Type": "application/json", "Authorization": "Token {}".format(settings.SERVICE_API_KEY)}
    data = {
        "email": consent["email"],
        "ubiquity_join_date": arrow.get(consent["timestamp"]).format("YYYY-MM-DD hh:mm:ss"),
    }
    requests.post(url=url, headers=headers, json=data)


def _delete_user_membership_cards(user: "CustomUser", send_deactivation: bool = True) -> None:
    cards_to_delete = []
    for card in user.scheme_account_set.prefetch_related("user_set").all():
        if card.user_set.count() == 1:
            card.is_deleted = True
            cards_to_delete.append(card)

    user_card_entries = user.schemeaccountentry_set.all()

    for user_card_entry in user_card_entries:
        scheme_account = user_card_entry.scheme_account
        remove_loyalty_card_event(user, scheme_account)

    # VOP deactivate
    links_to_remove = PaymentCardSchemeEntry.objects.filter(scheme_account__in=cards_to_delete)
    if send_deactivation:
        vop_links = links_to_remove.filter(payment_card_account__payment_card__slug="visa")
        activations = VopActivation.find_activations_matching_links(vop_links)
        PaymentCardSchemeEntry.deactivate_activations(activations)

    # TODO check if signal picks up queryset.delete()
    links_to_remove.delete()
    history_bulk_update(SchemeAccount, cards_to_delete, ["is_deleted"])
    user_card_entries.delete()


def _delete_user_payment_cards(user: "CustomUser", run_async: bool = True) -> None:
    cards_to_delete = []
    for card in user.payment_card_account_set.prefetch_related("user_set").all():
        if card.user_set.count() == 1:
            card.is_deleted = True
            cards_to_delete.append(card)
            metis.delete_payment_card(card, run_async=run_async)

    # TODO check if signal picks up queryset.delete()
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
                "event_date_time": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f"),
                "external_user_ref": user.external_id,
                "internal_user_ref": user.id,
                "email": user.email,
                "payment_account_id": pay_card.id,
                "fingerprint": pay_card.fingerprint,
                "expiry_date": f"{pay_card.expiry_month}/{pay_card.expiry_year}",
                "token": pay_card.token,
                "status": pay_card.status,
            }
            to_data_warehouse(payload)

        history_bulk_update(PaymentCardAccount, cards_to_delete, ["is_deleted"])
        user_card_entry.delete()


@shared_task
def deleted_service_cleanup(user_id: int, consent: dict, history_kwargs: dict = None) -> None:
    set_history_kwargs(history_kwargs)
    user = CustomUser.all_objects.get(id=user_id)
    user.serviceconsent.delete()
    # Don't deactivate when removing membership card as it will race with delete payment card
    # Deleting all payment cards causes an unenrol for each card which also deactivates all linked activations
    # if a payment card was linked to 2 accounts its activations will not be deleted
    _delete_user_membership_cards(user, send_deactivation=False)
    _delete_user_payment_cards(user, run_async=False)
    clean_history_kwargs(history_kwargs)

    try:  # send user info to be persisted in Atlas
        _send_data_to_atlas(consent)
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


@shared_task
def auto_link_membership_to_payments(
    payment_cards_to_link: list, membership_card: t.Union[SchemeAccount, int], history_kwargs: dict = None
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
        .exclude(id__in=excluded_payment_cards)
        .select_related("payment_card")
        .all()
    )

    link_entries_to_create = []
    pll_activated_payment_cards = []
    vop_activated_cards = []
    for payment_card_account in payment_cards_to_link:
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


def _get_instances_to_bulk_create(
    payment_card_account: PaymentCardAccount, wallet_scheme_accounts: list, just_created: bool
) -> dict:
    if just_created:
        already_linked_scheme_ids = []
    else:
        already_linked_scheme_ids = PaymentCardSchemeEntry.objects.filter(
            payment_card_account=payment_card_account
        ).values_list("scheme_account__scheme_id", flat=True)

    cards_by_scheme_ids = {}
    instances_to_bulk_create = {}
    for scheme_account in wallet_scheme_accounts:
        scheme_id = scheme_account.scheme_id
        link = PaymentCardSchemeEntry(scheme_account=scheme_account, payment_card_account=payment_card_account)
        if scheme_id not in already_linked_scheme_ids:
            if scheme_id in cards_by_scheme_ids:
                if cards_by_scheme_ids[scheme_id] > scheme_account.id:
                    cards_by_scheme_ids[scheme_id] = scheme_account.id
                    instances_to_bulk_create[scheme_id] = link.get_instance_with_active_status()
            else:
                cards_by_scheme_ids[scheme_id] = scheme_account.id
                instances_to_bulk_create[scheme_id] = link.get_instance_with_active_status()

    return instances_to_bulk_create


@shared_task
def auto_link_payment_to_memberships(
    wallet_scheme_accounts: list,
    payment_card_account: t.Union[PaymentCardAccount, int],
    just_created: bool,
    history_kwargs: dict = None,
) -> None:
    set_history_kwargs(history_kwargs)

    if isinstance(payment_card_account, int):
        payment_card_account = PaymentCardAccount.objects.select_related("payment_card").get(pk=payment_card_account)

    if isinstance(wallet_scheme_accounts[0], int):
        wallet_scheme_accounts = SchemeAccount.objects.filter(id__in=wallet_scheme_accounts).all()

    instances_to_bulk_create = _get_instances_to_bulk_create(payment_card_account, wallet_scheme_accounts, just_created)
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

    clean_history_kwargs(history_kwargs)
