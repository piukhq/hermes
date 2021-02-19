from threading import local
from typing import Tuple, Optional

import sentry_sdk
from django.db.models import signals
from django.utils import timezone

from history.enums import ExcludedField, DeleteField
from history.models import HistoricalBase, get_required_extra_fields
from history.serializers import get_body_serializer
from history.tasks import record_history

HISTORY_CONTEXT = local()
EXCLUDED_FIELDS = ExcludedField.as_set()


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
        if hasattr(instance, DeleteField.IS_DELETED.value):
            deleted_key, deleted_value = DeleteField.IS_DELETED.get_value(instance)
        elif hasattr(instance, DeleteField.IS_ACTIVE.value):
            deleted_key, deleted_value = DeleteField.IS_ACTIVE.get_value(instance)
        else:
            deleted_key, deleted_value = DeleteField.NONE.get_value()

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

        elif deleted_key in update_fields and deleted_value:
            change_type = HistoricalBase.DELETE

        else:
            change_type = HistoricalBase.UPDATE
            change_details = ", ".join(update_fields)

    return change_type, change_details


def get_user_and_channel() -> Tuple[Optional[int], str]:
    request = getattr(HISTORY_CONTEXT, "request", None)
    if hasattr(HISTORY_CONTEXT, "user_info"):
        user_id, channel = HISTORY_CONTEXT.user_info

    elif hasattr(request, "user") and str(request.user) != "AnonymousUser":
        user_id = request.user.id
        channel = "django_admin"

    else:
        user_id = None
        channel = "internal_service"

    return user_id, channel


def signal_record_history(sender, instance, **kwargs) -> None:
    with sentry_sdk.start_span(op="signal", description="signal_record_history"):
        created_at = timezone.now()
        change_type, change_details = _get_change_type_and_details(instance, kwargs)
        if not change_type:
            return None

        instance_id = instance.id
        model_name = sender.__name__

        user_id, channel = get_user_and_channel()
        required_extra_fields = get_required_extra_fields(model_name)
        extra = {"user_id": user_id, "channel": channel}

        if "body" in required_extra_fields:
            extra["body"] = get_body_serializer(model_name)(instance).data

        if "journey" in required_extra_fields and hasattr(HISTORY_CONTEXT, "journey"):
            extra["journey"] = HISTORY_CONTEXT.journey
            del HISTORY_CONTEXT.journey

        for field in required_extra_fields:
            if field not in extra and hasattr(instance, field):
                extra[field] = getattr(instance, field)

        record_history.delay(
            model_name,
            created=created_at,
            change_type=change_type,
            change_details=change_details,
            instance_id=instance_id,
            **extra
        )
