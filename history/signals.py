from datetime import datetime
from threading import local

from django.db.models import signals

from history.enums import HistoryModel
from history.models import HistoricalBase
from history.serializers import get_body_serializer
from history.tasks import record_history
from user.authentication import ServiceUser

HISTORY_CONTEXT = local()


def _get_change_type_and_details(instance, kwargs):
    change_details = ""
    if kwargs.get("signal") == signals.pre_delete:
        change_type = HistoricalBase.DELETE

    else:
        update_fields = kwargs.get("update_fields")
        if update_fields and "is_deleted" in update_fields and instance.is_deleted:
            change_type = HistoricalBase.DELETE

        elif kwargs.get("created"):
            change_type = HistoricalBase.CREATE

        else:
            change_type = HistoricalBase.UPDATE
            try:
                change_details = ", ".join(kwargs["update_fields"])
            except (KeyError, TypeError):
                pass

    return change_type, change_details


def signal_record_history(sender, instance, **kwargs):
    created_at = datetime.utcnow()
    change_type, change_details = _get_change_type_and_details(instance, kwargs)

    instance_id = instance.id
    model_name = sender.__name__
    request = getattr(HISTORY_CONTEXT, "request", None)

    if hasattr(HISTORY_CONTEXT, "channels_permit"):
        user_id = HISTORY_CONTEXT.channels_permit.user.id
        channel = HISTORY_CONTEXT.channels_permit.bundle_id

    elif hasattr(request, "user") and request.user != ServiceUser:
        user_id = HISTORY_CONTEXT.request.user.id
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


for sender in HistoryModel:
    signals.pre_save.connect(signal_record_history, sender=sender.value)
    signals.pre_delete.connect(signal_record_history, sender=sender.value)
