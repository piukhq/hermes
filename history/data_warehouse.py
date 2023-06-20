import logging
import typing as t

import arrow
from django.conf import settings

from api_messaging.message_broker import SendingService

if t.TYPE_CHECKING:
    from scheme.models import SchemeAccount
    from ubiquity.models import PllUserAssociation, SchemeAccountEntry
    from user.models import CustomUser

logger = logging.getLogger("messaging")

message_sender = SendingService(
    dsn=settings.RABBIT_DSN,
    log_to=logger,
)


def get_main_answer(scheme_account: "SchemeAccount") -> str:
    return scheme_account.card_number or scheme_account.barcode or scheme_account.alt_main_answer


def to_data_warehouse(payload: dict) -> None:
    headers = {}
    if payload:
        message_sender.send(payload, headers, settings.WAREHOUSE_QUEUE_NAME)


def addauth_request_lc_event(
    user: "CustomUser", scheme_account: "SchemeAccount", bundle_id: str, date_time: object = None
):
    payload = {
        "event_type": "lc.addandauth.request",
        "origin": "channel",
        "channel": bundle_id,
        "event_date_time": date_time if date_time else arrow.utcnow().isoformat(),
        "external_user_ref": user.external_id,
        "internal_user_ref": user.id,
        "email": user.email,
        "scheme_account_id": scheme_account.id,
        "loyalty_plan": scheme_account.scheme_id,
        "main_answer": get_main_answer(scheme_account),
    }
    to_data_warehouse(payload)


def auth_request_lc_event(
    user: "CustomUser", scheme_account: "SchemeAccount", bundle_id: str, date_time: object = None
):
    payload = {
        "event_type": "lc.auth.request",
        "origin": "channel",
        "channel": bundle_id,
        "event_date_time": date_time if date_time else arrow.utcnow().isoformat(),
        "external_user_ref": user.external_id,
        "internal_user_ref": user.id,
        "email": user.email,
        "scheme_account_id": scheme_account.id,
        "loyalty_plan": scheme_account.scheme_id,
        "main_answer": get_main_answer(scheme_account),
    }
    to_data_warehouse(payload)


def register_lc_event(scheme_account_entry: "SchemeAccountEntry", bundle_id: str, date_time: object = None):
    payload = {
        "event_type": "lc.register.request",
        "origin": "channel",
        "channel": bundle_id,
        "event_date_time": date_time if date_time else arrow.utcnow().isoformat(),
        "external_user_ref": scheme_account_entry.user.external_id,
        "internal_user_ref": scheme_account_entry.user.id,
        "email": scheme_account_entry.user.email,
        "scheme_account_id": scheme_account_entry.scheme_account.id,
        "loyalty_plan": scheme_account_entry.scheme_account.scheme_id,
        "main_answer": get_main_answer(scheme_account_entry.scheme_account),
    }
    to_data_warehouse(payload)


def join_request_lc_event(scheme_account_entry: "SchemeAccountEntry", bundle_id: str, date_time: object = None):
    payload = {
        "event_type": "lc.join.request",
        "origin": "channel",
        "channel": bundle_id,
        "event_date_time": date_time if date_time else arrow.utcnow().isoformat(),
        "external_user_ref": scheme_account_entry.user.external_id,
        "internal_user_ref": scheme_account_entry.user.id,
        "email": scheme_account_entry.user.email,
        "scheme_account_id": scheme_account_entry.scheme_account.id,
        "loyalty_plan": scheme_account_entry.scheme_account.scheme_id,
    }
    to_data_warehouse(payload)


def remove_loyalty_card_event(scheme_account_entry: "SchemeAccountEntry", date_time: object = None):

    user = scheme_account_entry.user
    scheme_account = scheme_account_entry.scheme_account
    cabs = user.client.clientapplicationbundle_set.all()
    for cab in cabs:
        payload = {
            "event_type": "lc.removed",
            "origin": "channel",
            "channel": cab.bundle_id,
            "event_date_time": date_time if date_time else arrow.utcnow().isoformat(),
            "external_user_ref": user.external_id,
            "internal_user_ref": user.id,
            "email": user.email,
            "scheme_account_id": scheme_account.id,
            "loyalty_plan": scheme_account.scheme_id,
            "main_answer": get_main_answer(scheme_account),
            "status": scheme_account_entry.link_status,
        }
        to_data_warehouse(payload)


def join_outcome(success: bool, scheme_account_entry: "SchemeAccountEntry", date_time: object = None):
    extra_data = {}
    if success:
        event_type = "lc.join.success"
        extra_data["main_answer"] = get_main_answer(scheme_account_entry.scheme_account)
    else:
        event_type = "lc.join.failed"

    extra_data["status"] = scheme_account_entry.link_status

    cabs = scheme_account_entry.user.client.clientapplicationbundle_set.all()
    for cab in cabs:
        payload = {
            "event_type": event_type,
            "origin": "merchant.callback",
            "channel": cab.bundle_id,
            "event_date_time": date_time if date_time else arrow.utcnow().isoformat(),
            "external_user_ref": scheme_account_entry.user.external_id,
            "internal_user_ref": scheme_account_entry.user.id,
            "email": scheme_account_entry.user.email,
            "scheme_account_id": scheme_account_entry.scheme_account.id,
            "loyalty_plan": scheme_account_entry.scheme_account.scheme_id,
            **extra_data,
        }
        to_data_warehouse(payload)


def add_auth_outcome(success: bool, scheme_account_entry: "SchemeAccountEntry", date_time: object = None):
    extra_data = {}
    if success:
        event_type = "lc.addandauth.success"
        extra_data["main_answer"] = get_main_answer(scheme_account_entry.scheme_account)
    else:
        event_type = "lc.addandauth.failed"

    extra_data["status"] = scheme_account_entry.link_status

    payload = {
        "event_type": event_type,
        "origin": "channel",
        "channel": scheme_account_entry.user.bundle_id,
        "event_date_time": date_time if date_time else arrow.utcnow().isoformat(),
        "external_user_ref": scheme_account_entry.user.external_id,
        "internal_user_ref": scheme_account_entry.user.id,
        "email": scheme_account_entry.user.email,
        "scheme_account_id": scheme_account_entry.scheme_account.id,
        "loyalty_plan": scheme_account_entry.scheme_account.scheme_id,
        **extra_data,
    }
    to_data_warehouse(payload)


def auth_outcome(success: bool, scheme_account_entry: "SchemeAccountEntry", date_time: object = None):
    extra_data = {}
    if success:
        event_type = "lc.auth.success"
        extra_data["main_answer"] = get_main_answer(scheme_account_entry.scheme_account)
    else:
        event_type = "lc.auth.failed"

    extra_data["status"] = scheme_account_entry.link_status

    payload = {
        "event_type": event_type,
        "origin": "channel",
        "channel": scheme_account_entry.user.bundle_id,
        "event_date_time": date_time if date_time else arrow.utcnow().isoformat(),
        "external_user_ref": scheme_account_entry.user.external_id,
        "internal_user_ref": scheme_account_entry.user.id,
        "email": scheme_account_entry.user.email,
        "scheme_account_id": scheme_account_entry.scheme_account.id,
        "loyalty_plan": scheme_account_entry.scheme_account.scheme_id,
        **extra_data,
    }
    to_data_warehouse(payload)


def register_outcome(success: bool, scheme_account_entry: "SchemeAccountEntry", date_time: object = None):
    extra_data = {}
    if success:
        event_type = "lc.register.success"
        extra_data["main_answer"] = get_main_answer(scheme_account_entry.scheme_account)
    else:
        event_type = "lc.register.failed"

    extra_data["status"] = scheme_account_entry.link_status

    cabs = scheme_account_entry.user.client.clientapplicationbundle_set.all()
    for cab in cabs:
        payload = {
            "event_type": event_type,
            "origin": "merchant.callback",
            "channel": cab.bundle_id,
            "event_date_time": date_time if date_time else arrow.utcnow().isoformat(),
            "external_user_ref": scheme_account_entry.user.external_id,
            "internal_user_ref": scheme_account_entry.user.id,
            "email": scheme_account_entry.user.email,
            "scheme_account_id": scheme_account_entry.scheme_account.id,
            "loyalty_plan": scheme_account_entry.scheme_account.scheme_id,
            **extra_data,
        }
        to_data_warehouse(payload)


def pay_account_from_entry(data: dict) -> list:
    from payment_card.models import PaymentCardAccount
    from user.models import CustomUser

    pay_card_account = PaymentCardAccount.all_objects.get(id=data.get("payment_card_account_id"))
    # Note on delete payment card account has already been marked deleted and the association with
    # user has also been deleted.

    user = CustomUser.all_objects.get(id=data.get("user_id"))
    extra_data = []

    cabs = user.client.clientapplicationbundle_set.all()
    for cab in cabs:
        extra_data.append(
            {
                "external_user_ref": user.external_id,
                "internal_user_ref": user.id,
                "email": user.email,
                "channel": cab.bundle_id,
                "payment_account_id": pay_card_account.id,
                "fingerprint": pay_card_account.fingerprint,
                "expiry_date": f"{pay_card_account.expiry_month:02d}/{pay_card_account.expiry_year:02d}",
                "token": pay_card_account.token,
                "status": pay_card_account.status,
            }
        )
    return extra_data


def scheme_account_entry_status_update(data: dict) -> list:
    from ubiquity.models import SchemeAccountEntry

    # One day we might want to include in the report which user has caused the event ie
    # by_user_id = data.get("user_id")
    # if by_user_id:
    #    by_user_info = CustomUser.objects.get(id=user_id)

    extras = []
    if data.get("link_status", False):
        sae = SchemeAccountEntry.objects.select_related("scheme_account", "scheme_account__scheme", "user").get(
            id=data.get("instance_id")
        )
        user = sae.user
        scheme_account = sae.scheme_account
        cabs = user.client.clientapplicationbundle_set.all()

        for cab in cabs:
            extra_data = {
                "external_user_ref": user.external_id,
                "internal_user_ref": user.id,
                "email": user.email,
                "scheme_account_id": scheme_account.id,
                "loyalty_plan": scheme_account.scheme.id,
                "main_answer": get_main_answer(scheme_account),
                "to_status": data["link_status"],
                "channel": cab.bundle_id,
            }
            extras.append(extra_data)
    return extras


def user_data(data: dict) -> list:
    from user.models import CustomUser

    extra_data = []
    user = CustomUser.all_objects.get(id=data.get("instance_id"))
    cabs = user.client.clientapplicationbundle_set.all()
    for cab in cabs:
        extra_data.append(
            {
                "external_user_ref": user.external_id,
                "internal_user_ref": user.id,
                "email": user.email,
                "channel": cab.bundle_id,
            }
        )
    return extra_data


event_map = {
    "PaymentCardAccountEntry": {
        "create": ("payment.account.added", pay_account_from_entry),
        "delete": ("payment.account.removed", pay_account_from_entry),
    },
    "CustomUser": {"create": ("user.created", user_data), "delete": ("user.deleted", user_data)},
    "SchemeAccountEntry": {
        "update": ("lc.statuschange", scheme_account_entry_status_update),
    },
}


def history_event(model_name: str, data: dict):
    if model_name in event_map and data.get("change_type") in event_map.get(model_name, {}):
        event_info = event_map[model_name][data["change_type"]]
        origin = "channel"
        by_channel_slug = data.get("channel")
        if by_channel_slug == "django_admin":
            origin = "django_admin"
            by_channel_slug = ""
        elif by_channel_slug == "internal_service":
            # todo since we could confirm using thread.local/history_kwargs that the internal_service has really
            #  occurred we might want to distinguish between "merchant.callback" and other causes. However this has
            #  not been agreed with the Data team
            origin = "merchant.callback"
            by_channel_slug = ""
        # Note by_channel_slug is the channel in which event occurred and is not currently reported instead every
        # channel affected will be reported in the extra datas dict.
        if event_info[1]:
            extra_datas = event_info[1](data)
            for extra_data in extra_datas:
                # These next 2 lines are not really necessary as the channel should always be present.
                # In future we might want to report the channel_slug and the by_channel_slug
                # i.e. remove next two lines and add extra_data['by_channel'] = by_channel_slug
                if not extra_data.get("channel"):
                    extra_data["channel"] = by_channel_slug
                payload = {
                    "event_type": event_info[0],
                    "origin": origin,
                    "event_date_time": arrow.utcnow().isoformat(),
                    **extra_data,
                }
                to_data_warehouse(payload)


def user_pll_status_change_event(
    user_pll: "PllUserAssociation", previous_slug: str, previous_state: int = None
) -> None:
    # Only trigger an event when there's a state change or slug change
    if previous_state != user_pll.state or previous_slug != user_pll.slug:
        payload = {
            "event_type": "pll_link.statuschange",
            "origin": "channel",
            "channel": user_pll.user.client_id,
            "event_date_time": arrow.utcnow().isoformat(),
            "external_user_ref": user_pll.user.external_id,
            "internal_user_ref": user_pll.user_id,
            "email": user_pll.user.email,
            "payment_account_id": user_pll.pll.payment_card_account_id,
            "scheme_account_id": user_pll.pll.scheme_account_id,
            "slug": user_pll.slug,
            "from_state": previous_state,
            "to_state": user_pll.state,
        }
        to_data_warehouse(payload)


def generate_pll_delete_payload(user_plls: list["PllUserAssociation"]):
    event_payloads = []

    for user_pll in user_plls:
        event_payloads.append(
            {
                "event_type": "pll_link.statuschange",
                "origin": "channel",
                "channel": user_pll.user.client_id,
                "event_date_time": arrow.utcnow().isoformat(),
                "external_user_ref": user_pll.user.external_id,
                "internal_user_ref": user_pll.user_id,
                "email": user_pll.user.email,
                "payment_account_id": user_pll.pll.payment_card_account_id,
                "scheme_account_id": user_pll.pll.scheme_account_id,
                "slug": user_pll.slug,
                "from_state": user_pll.state,
                "to_state": None,
            }
        )

    return event_payloads


def user_pll_delete_event(payloads: list[dict]) -> None:
    for payload in payloads:
        to_data_warehouse(payload)
