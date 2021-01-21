from threading import local

from django.db.models import signals
from django.utils import timezone

from history.enums import HistoryModel, ExcludedFields
from history.models import HistoricalBase
from history.serializers import get_body_serializer
from history.tasks import record_history
from user.authentication import ServiceUser

HISTORY_CONTEXT = local()
EXCLUDED_FIELDS = ExcludedFields.as_set()


def _get_change_type_and_details(instance, kwargs):
    """
    Expected behaviour:
    Card has been created: returns "create", ""
    Card has been deleted or soft deleted: returns "delete", ""
    Card has been updated: returns "update", comma separated list of updated fields es: "barcode, card number"
    Only ExcludedFields have been updated: returns None, ""
    """

    change_details = ""
    if kwargs.get("signal") == signals.pre_delete:
        change_type = HistoricalBase.DELETE

    else:
        update_fields = kwargs.get("update_fields")
        if update_fields:
            if set(update_fields) <= EXCLUDED_FIELDS:
                return None, change_details

            else:
                update_fields = set(update_fields) - EXCLUDED_FIELDS
        else:
            update_fields = set()

        if kwargs.get("created"):
            change_type = HistoricalBase.CREATE

        elif "is_deleted" in update_fields and instance.is_deleted:
            change_type = HistoricalBase.DELETE

        else:
            change_type = HistoricalBase.UPDATE
            change_details = ", ".join(update_fields)

    return change_type, change_details


def signal_record_history(sender, instance, **kwargs) -> None:
    created_at = timezone.now()
    change_type, change_details = _get_change_type_and_details(instance, kwargs)
    if not change_type:
        return None

    instance_id = instance.id
    model_name = sender.__name__
    request = getattr(HISTORY_CONTEXT, "request", None)

    if hasattr(HISTORY_CONTEXT, "user_info"):
        user_id, channel = HISTORY_CONTEXT.user_info

    elif hasattr(request, "user") and request.user.uid != ServiceUser.uid:
        user_id = request.user.id
        channel = "django_admin"

    else:
        user_id = None
        channel = "internal_service"

    extra = {"user_id": user_id, "channel": channel}

    if model_name in [HistoryModel.PAYMENT_CARD_ACCOUNT, HistoryModel.SCHEME_ACCOUNT]:
        extra["body"] = get_body_serializer(model_name)(instance).data

        if model_name == HistoryModel.SCHEME_ACCOUNT and hasattr(HISTORY_CONTEXT, "journey"):
            extra["journey"] = HISTORY_CONTEXT.journey
            del HISTORY_CONTEXT.journey

    else:
        if hasattr(instance, "payment_card_account_id"):
            extra["payment_card_account_id"] = instance.payment_card_account_id

        if hasattr(instance, "scheme_account_id"):
            extra["scheme_account_id"] = instance.scheme_account_id

    record_history.delay(
        model_name,
        created=created_at,
        change_type=change_type,
        change_details=change_details,
        instance_id=instance_id,
        **extra
    )
