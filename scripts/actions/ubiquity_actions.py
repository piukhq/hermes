import logging
import typing

from django.db import transaction

from payment_card.models import PaymentCardAccount
from ubiquity.models import PaymentCardSchemeEntry
from ubiquity.tasks import deleted_service_cleanup
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
    success = True
    try:
        user = CustomUser.all_objects.select_related("serviceconsent").get(pk=entry.data["user_id"])

        consent_data = None
        try:
            consent = user.serviceconsent
            consent_data = {"email": user.email, "timestamp": consent.timestamp}
        except CustomUser.serviceconsent.RelatedObjectDoesNotExist:
            logger.error(f"Service Consent data could not be found whilst deleting user {user.id} .")

        if user.is_active:
            user.soft_delete()
            deleted_service_cleanup(user_id=user.id, consent=consent_data)
            logger.info(f"User {user.id} successfully deleted.")
        else:
            deleted_service_cleanup(user_id=user.id, consent=consent_data)
            logger.info(f"User {user.id} already deleted, but delete cleanup has run successfully")
    except CustomUser.DoesNotExist:
        pass
    except Exception as e:
        logger.exception(e)
        success = False

    return success
