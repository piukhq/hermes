from datetime import datetime
from threading import local

from django.db.models import signals

from history.models import HistoricalBase, HistoricalSchemeAccount
from history.serializers import get_body_serializer
from history.tasks import record_history

HISTORY_MODELS = [
    "payment_card.PaymentCardAccount",
    "ubiquity.PaymentCardAccountEntry",
    "scheme.SchemeAccount",
    "ubiquity.SchemeAccountEntry",
]

LOCAL_CONTEXT = local()


def _get_change_type_and_details(kwargs):
    change_details = ""
    if kwargs.get("signal") == signals.pre_delete:
        change_type = HistoricalBase.DELETE

    else:
        update_fields = kwargs.get("update_fields")
        if update_fields and "is_deleted" in update_fields:
            change_type = HistoricalBase.DELETE

        elif kwargs.get("created"):
            change_type = HistoricalBase.CREATE

        else:
            change_type = HistoricalBase.UPDATE
            change_details = ", ".join(kwargs.get("update_fields"))

    return change_type, change_details


def signal_record_history(sender, instance, **kwargs):
    created_at = datetime.utcnow()
    change_type, change_details = _get_change_type_and_details(kwargs)

    instance_id = instance.id
    model_name = sender.__name__

    if hasattr(LOCAL_CONTEXT, "channels_permit"):
        user_id = LOCAL_CONTEXT.channels_permit.user.id
        channel = LOCAL_CONTEXT.channels_permit.bundle_id
    else:
        user_id = None
        channel = "internal_service"

    extra = {
        "user_id": user_id,
        "channel": channel
    }

    # TODO  enums! we have PaymentCardAccount etc repeated everywhere
    if model_name in ["PaymentCardAccount", "SchemeAccount"]:
        extra["body"] = get_body_serializer[model_name](instance).data

        if model_name == "SchemeAccount":
            extra["journey"] = HistoricalSchemeAccount.ADD

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


for sender in HISTORY_MODELS:
    signals.post_save.connect(signal_record_history, sender=sender)
    signals.pre_delete.connect(signal_record_history, sender=sender)
