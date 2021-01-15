from datetime import datetime

from django.db.models import signals

from history.models import HistoricalBase
from history.serializers import get_body_serializer
from history.tasks import record_history

HISTORY_MODELS = [
    "payment_card.PaymentCardAccount",
    "ubiquity.PaymentCardAccountEntry",
]


def _get_change_type(kwargs):
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

    return change_type


def signal_record_history(sender, instance, **kwargs):
    created_at = datetime.utcnow()
    change_type = _get_change_type(kwargs)
    instance_id = instance.id
    model_name = sender.__name__

    # TODO  enums! we have PaymentCardAccount etc repeated everywhere
    # TODO collect channel and user id from channels_permit
    if model_name in ["PaymentCardAccount", "SchemeAccount"]:
        extra = {"body": get_body_serializer[model_name](instance).data}

    else:
        extra = {
            "user_id": instance.user_id,
            "channel": instance.user.client.clientapplicationbundle_set.values_list("bundle_id", flat=True).first()
        }
        if hasattr(instance, "payment_card_account_id"):
            extra["payment_card_account_id"] = instance.payment_card_account_id
        elif hasattr(instance, "scheme_account_id"):
            extra["scheme_account_id"]: instance.scheme_account_id

    record_history.delay(
        model_name,
        created=created_at,
        change_type=change_type,
        instance_id=instance_id,
        **extra
    )


for sender in HISTORY_MODELS:
    signals.post_save.connect(signal_record_history, sender=sender)
    signals.pre_delete.connect(signal_record_history, sender=sender)
