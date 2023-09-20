import logging
import typing
from datetime import UTC, datetime
from typing import cast

from django.db import transaction

from history.utils import user_info
from payment_card.models import PaymentCardAccount
from scheme.models import SchemeAccount
from ubiquity.models import PaymentCardSchemeEntry, SchemeAccountEntry, ServiceConsent
from ubiquity.tasks import deleted_membership_card_cleanup, deleted_service_cleanup
from user.models import CustomUser

if typing.TYPE_CHECKING:
    from scripts.models import ScriptResult

logger = logging.getLogger(__name__)


def do_update_active_link_to_false(entry: "ScriptResult") -> bool:
    try:
        with transaction.atomic():
            payment_scheme_entry = PaymentCardSchemeEntry.objects.select_for_update().get(
                id=entry.data["paymentcardschemeentry_id"]
            )
            payment_scheme_entry.active_link = False
            payment_scheme_entry.save(update_fields=["active_link"])

        return True

    except Exception:
        return False


def do_delete_user_cleanup(entry: "ScriptResult") -> bool:
    success = False
    try:
        # This script is to just do the deletion cleanup of card links. There would have already been
        # a delete request which would have deleted the consent data so there's no point in looking it
        # up to delete and send to atlas.
        deleted_service_cleanup(user_id=entry.data["user_id"], consent={})
        success = True

    except KeyError:
        logger.exception(f"The script result data is missing the user_id for ScriptResult(id={entry.id})")
    except Exception:
        logger.exception(f"An unexpected error occurred when running correction script for ScriptResult(id={entry.id})")

    return success


def do_set_account_and_links_active(entry: "ScriptResult") -> bool:
    pca = PaymentCardAccount.objects.get(pk=entry.data["card_id"])
    pca.status = PaymentCardAccount.ACTIVE
    pca.save(update_fields=["status"])
    return True


def do_client_decommission(entry: "ScriptResult") -> bool:
    consent_data: "dict[str, str | datetime] | None" = None
    success = True
    try:
        user = cast(CustomUser, CustomUser.all_objects.select_related("serviceconsent").get(pk=entry.data["user_id"]))

        try:
            consent = cast(ServiceConsent, user.serviceconsent)
            consent_data = {"email": user.email, "timestamp": consent.timestamp}
        except CustomUser.serviceconsent.RelatedObjectDoesNotExist:
            logger.error("Service Consent data could not be found whilst deleting user %d .", user.id)

        if user.is_active:
            user.soft_delete()
            msg = "User %d successfully deleted."
        else:
            msg = "User %d already deleted, but delete cleanup has run successfully"

        deleted_service_cleanup(user_id=user.id, consent=consent_data, user=user)
        logger.info(msg, user.id)
    except CustomUser.DoesNotExist:
        pass
    except Exception as e:
        logger.exception("Unexpected error.", exc_info=e)
        success = False

    return success


def do_channel_retailer_offboarding(entry: "ScriptResult") -> bool:
    success = False

    try:
        scheme_account_id = cast(int, entry.data["scheme_account_id"])
        client_channel_map = cast(dict[str, dict[str, str]], entry.data["client_channel_map"])

        for scheme_account_entry in (
            SchemeAccountEntry.objects.select_related("scheme_account__scheme", "user")
            .filter(scheme_account_id=scheme_account_id, user__client_id__in=client_channel_map.keys())
            .all()
        ):
            deleted_membership_card_cleanup(
                scheme_account_entry=scheme_account_entry,
                delete_date=datetime.now(tz=UTC).isoformat(),
                history_kwargs={
                    "user_info": user_info(
                        user_id=scheme_account_entry.user_id,
                        channel=client_channel_map[scheme_account_entry.user.client_id]["channel"],
                    )
                },
            )

        success = True

    except SchemeAccount.DoesNotExist:
        logger.warn("Script result scheme account id '%d' does not exist", scheme_account_id)
    except Exception as e:
        logger.exception("Unexpected error", exc_info=e)
        success = False

    return success
