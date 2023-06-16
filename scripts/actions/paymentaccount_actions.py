import logging

from payment_card.enums import RequestMethod
from payment_card.models import PaymentCardAccount
from ubiquity.models import PaymentCardAccountEntry, PaymentCardSchemeEntry

from .metis_foundation import metis_foundation_request

logger = logging.getLogger(__name__)


def do_retain(entry: dict) -> bool:
    card = PaymentCardAccount.objects.get(id=entry.data["card_id"])
    data = {"payment_token": entry.data["payment_token"], "id": entry.data["card_id"]}
    reply = metis_foundation_request(RequestMethod.POST, f"/foundation/spreedly/{card.payment_card.slug}/retain", data)
    return reply.get("status_code") == 200 and reply.get("reason") == "OK"


def do_re_enroll(entry: dict) -> bool:
    try:
        data = {
            "payment_token": entry.data["payment_token"],
            "id": entry.data["card_id"],
            "card_token": entry.data["card_token"],
            "partner_slug": entry.data["partner_slug"],
        }
        reply = metis_foundation_request(
            RequestMethod.POST, f"/foundation/spreedly/{entry.data['partner_slug']}/add", data
        )
        if (
            data["partner_slug"] == "visa"
            and reply.get("agent_response_code") == "Add:SUCCESS"
            and reply.get("status_code") == 201
        ):
            return True
        elif 200 <= reply["status_code"] < 300:
            return True
        return False
    except Exception as ex:
        logger.warning(ex)
        return False


def do_un_enroll(entry: dict) -> bool:
    try:
        data = {
            "payment_token": entry.data["payment_token"],
            "id": entry.data["card_id"],
            "partner_slug": entry.data["partner_slug"],
        }
        reply = metis_foundation_request(RequestMethod.POST, f"/foundation/{entry.data['partner_slug']}/remove", data)
        if (
            data["partner_slug"] == "visa"
            and reply.get("agent_response_code") == "Delete:SUCCESS"
            and reply.get("status_code") == 201
        ):
            return True
        elif 200 <= reply["status_code"] < 300:
            return True
        return False
    except Exception as ex:
        logger.warning(ex)
        return False


def do_update_hash(entry: dict) -> bool:
    try:
        acc = PaymentCardAccount.objects.get(id=entry.data["payment_card_account_id"])
        acc.hash = entry.data["new_hash"]
        acc.save(update_fields=["hash", "updated"])
        return True
    except Exception as ex:
        logger.warning(ex)
        return False


def do_remove_payment_account(entry: dict) -> bool:
    try:
        PaymentCardAccountEntry.objects.get(
            payment_card_account__id=entry.data["account_user_assoc_id"], user__id=entry.data["user_id"]
        ).delete()
        return True
    except Exception as ex:
        logger.warning(ex)
        return False


def do_delete_payment_account(entry: dict) -> bool:
    try:
        payment_card_account = PaymentCardAccount.objects.get(id=entry.data["payment_card_account_id"])
        payment_card_account.is_deleted = True
        payment_card_account.save(update_fields=["is_deleted"])
        return True
    except Exception as ex:
        logger.warning(ex)
        return False


def do_removed_payment_account_scheme_entry(entry: dict) -> bool:
    try:
        PaymentCardSchemeEntry.objects.filter(payment_card_account__id=entry.data["payment_card_account_id"]).delete()
        return True
    except Exception as ex:
        logger.warning(ex)
        return False
