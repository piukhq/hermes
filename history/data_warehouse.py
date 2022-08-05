import logging
import typing as t

import arrow
from django.conf import settings

from api_messaging.message_broker import SendingService

if t.TYPE_CHECKING:
    from user.models import CustomUser
    from scheme.models import SchemeAccount

logger = logging.getLogger("messaging")

message_sender = SendingService(
    dsn=settings.RABBIT_DSN,
    log_to=logger,
)


def to_data_warehouse(payload: dict) -> None:
    headers = {}
    if payload:
        message_sender.send(payload, headers, settings.WAREHOUSE_QUEUE_NAME)


def addauth_request_lc_event(user: "CustomUser", scheme_account: "SchemeAccount", bundle_id: str):
    payload = {
        "event_type": "lc.addandauth.request",
        "origin": "channel",
        "channel": bundle_id,
        "event_date_time": arrow.utcnow().isoformat(),
        "external_user_ref": user.external_id,
        "internal_user_ref": user.id,
        "email": user.email,
        "scheme_account_id": scheme_account.id,
        "loyalty_plan": scheme_account.scheme_id,
        "main_answer": scheme_account.main_answer,
    }
    to_data_warehouse(payload)


def auth_request_lc_event(user: CustomUser, scheme_account: "SchemeAccount", bundle_id: str):
    payload = {
        "event_type": "lc.auth.request",
        "origin": "channel",
        "channel": bundle_id,
        "event_date_time": arrow.utcnow().isoformat(),
        "external_user_ref": user.external_id,
        "internal_user_ref": user.id,
        "email": user.email,
        "scheme_account_id": scheme_account.id,
        "loyalty_plan": scheme_account.scheme_id,
        "main_answer": scheme_account.main_answer,
    }
    to_data_warehouse(payload)


def register_lc_event(user: "CustomUser", scheme_account: "SchemeAccount", bundle_id: str):
    payload = {
        "event_type": "lc.register.request",
        "origin": "channel",
        "channel": bundle_id,
        "event_date_time": arrow.utcnow().isoformat(),
        "external_user_ref": user.external_id,
        "internal_user_ref": user.id,
        "email": user.email,
        "scheme_account_id": scheme_account.id,
        "loyalty_plan": scheme_account.scheme_id,
        "main_answer": scheme_account.main_answer,
    }
    to_data_warehouse(payload)


def join_request_lc_event(user: "CustomUser", scheme_account: "SchemeAccount", bundle_id: str):
    payload = {
        "event_type": "lc.join.request",
        "origin": "channel",
        "channel": bundle_id,
        "event_date_time": arrow.utcnow().isoformat(),
        "external_user_ref": user.external_id,
        "internal_user_ref": user.id,
        "email": user.email,
        "scheme_account_id": scheme_account.id,
        "loyalty_plan": scheme_account.scheme_id,
    }
    to_data_warehouse(payload)


def remove_loyalty_card_event(user: "CustomUser", scheme_account: "SchemeAccount"):
    cabs = user.client.clientapplicationbundle_set.all()
    for cab in cabs:
        payload = {
            "event_type": "lc.removed",
            "origin": "channel",
            "channel": cab.bundle_id,
            "event_date_time": arrow.utcnow().isoformat(),
            "external_user_ref": user.external_id,
            "internal_user_ref": user.id,
            "email": user.email,
            "scheme_account_id": scheme_account.id,
            "loyalty_plan": scheme_account.scheme_id,
            "main_answer": scheme_account.main_answer,
            "status": scheme_account.status,
        }
        to_data_warehouse(payload)


def join_outcome(success: bool, user: "CustomUser", scheme_account: "SchemeAccount"):
    extra_data = {}
    if success:
        event_type = "lc.join.success"
        extra_data["main_answer"] = scheme_account.main_answer
    else:
        event_type = "lc.join.failed"

    extra_data["status"] = scheme_account.status

    cabs = user.client.clientapplicationbundle_set.all()
    for cab in cabs:
        payload = {
            "event_type": event_type,
            "origin": "merchant.callback",
            "channel": cab.bundle_id,
            "event_date_time": arrow.utcnow().isoformat(),
            "external_user_ref": user.external_id,
            "internal_user_ref": user.id,
            "email": user.email,
            "scheme_account_id": scheme_account.id,
            "loyalty_plan": scheme_account.scheme_id,
            **extra_data,
        }
        to_data_warehouse(payload)


def add_auth_outcome(success: bool, user: "CustomUser", scheme_account: "SchemeAccount"):
    extra_data = {}
    if success:
        event_type = "lc.addandauth.success"
        extra_data["main_answer"] = scheme_account.main_answer
    else:
        event_type = "lc.addandauth.failed"

    extra_data["status"] = scheme_account.status

    payload = {
        "event_type": event_type,
        "origin": "channel",
        "channel": user.bundle_id,
        "event_date_time": arrow.utcnow().isoformat(),
        "external_user_ref": user.external_id,
        "internal_user_ref": user.id,
        "email": user.email,
        "scheme_account_id": scheme_account.id,
        "loyalty_plan": scheme_account.scheme_id,
        **extra_data,
    }
    to_data_warehouse(payload)


def auth_outcome(success: bool, user: "CustomUser", scheme_account: "SchemeAccount"):
    extra_data = {}
    if success:
        event_type = "lc.auth.success"
        extra_data["main_answer"] = scheme_account.main_answer
    else:
        event_type = "lc.auth.failed"

    extra_data["status"] = scheme_account.status

    payload = {
        "event_type": event_type,
        "origin": "channel",
        "channel": user.bundle_id,
        "event_date_time": arrow.utcnow().isoformat(),
        "external_user_ref": user.external_id,
        "internal_user_ref": user.id,
        "email": user.email,
        "scheme_account_id": scheme_account.id,
        "loyalty_plan": scheme_account.scheme_id,
        **extra_data,
    }
    to_data_warehouse(payload)


def register_outcome(success: bool, user: "CustomUser", scheme_account: "SchemeAccount"):
    extra_data = {}
    if success:
        event_type = "lc.register.success"
        extra_data["main_answer"] = scheme_account.main_answer
    else:
        event_type = "lc.register.failed"

    extra_data["status"] = scheme_account.status

    cabs = user.client.clientapplicationbundle_set.all()
    for cab in cabs:
        payload = {
            "event_type": event_type,
            "origin": "merchant.callback",
            "channel": cab.bundle_id,
            "event_date_time": arrow.utcnow().isoformat(),
            "external_user_ref": user.external_id,
            "internal_user_ref": user.id,
            "email": user.email,
            "scheme_account_id": scheme_account.id,
            "loyalty_plan": scheme_account.scheme_id,
            **extra_data,
        }
        to_data_warehouse(payload)


def pay_account_from_entry(data: dict) -> list:
    from payment_card.models import PaymentCardAccount
    from user.models import CustomUser

    pay_card_account = PaymentCardAccount.objects.get(id=data.get("payment_card_account_id"))
    user_info = CustomUser.objects.get(id=data.get("user_id"))
    extra_data = {
        "external_user_ref": user_info.external_id,
        "internal_user_ref": user_info.id,
        "email": user_info.email,
        "payment_account_id": pay_card_account.id,
        "fingerprint": pay_card_account.fingerprint,
        "expiry_date": f"{pay_card_account.expiry_month}/{pay_card_account.expiry_year}",
        "token": pay_card_account.token,
        "status": pay_card_account.status,
    }
    return [extra_data]


def scheme_account_status_update(data: dict) -> list:
    from scheme.models import SchemeAccount
    from ubiquity.models import SchemeAccountEntry

    body = data.get("body", {})
    extras = []
    if "status" in data.get("change_details") and body:
        scheme_account_id = body.get("id")
        scheme_account = SchemeAccount.objects.get(id=scheme_account_id)
        wallets = SchemeAccountEntry.objects.filter(scheme_account=scheme_account).all()
        for wallet in wallets:
            user = wallet.user
            extra_data = {
                "external_user_ref": user.external_id,
                "internal_user_ref": user.id,
                "email": user.email,
                "scheme_account_id": scheme_account_id,
                "loyalty_plan": body.get("scheme"),
                "main_answer": body.get("main_answer"),
                "to_status": body.get("status"),
            }
            extras.append(extra_data)
    return extras


def user_data(data: dict) -> list:
    body = data.get("body", {})
    extra_data = {
        "external_user_ref": body.get("external_id"),
        "internal_user_ref": body.get("id"),
        "email": body.get("email"),
    }
    return [extra_data]


event_map = {
    "PaymentCardAccountEntry": {
        "create": ("payment.account.added", pay_account_from_entry),
        "delete": ("payment.account.removed", pay_account_from_entry),
    },
    "CustomUser": {"create": ("user.created", user_data), "delete": ("user.deleted", user_data)},
    "SchemeAccount": {
        "update": ("lc.statuschange", scheme_account_status_update),
    },
}


def history_event(model_name: str, data: dict):
    if model_name in event_map and data.get("change_type") in event_map.get(model_name, {}):
        event_info = event_map[model_name][data["change_type"]]
        origin = "channel"
        channel_slug = data.get("channel")
        if channel_slug == "django_admin":
            origin = "django_admin"
            channel_slug = ""
        elif channel_slug == "internal_service":
            # todo we will need to confirm using thread.local/history_kwargs that the internal_service has occurred
            #  due to a merchant callback and decide what to do if it is due to some other cause
            origin = "merchant.callback"
            channel_slug = ""
        extra_datas = []
        if event_info[1]:
            extra_datas = event_info[1](data)
            for extra_data in extra_datas:
                payload = {
                    "event_type": event_info[0],
                    "origin": origin,
                    "channel": channel_slug,
                    "event_date_time": arrow.utcnow().isoformat(),
                    **extra_data,
                }
                to_data_warehouse(payload)
