from celery import shared_task

from history.serializers import get_history_serializer


@shared_task
def record_history(model_name, **kwargs):
    serializer = get_history_serializer[model_name](data=kwargs)

    if "user_id" not in kwargs:
        kwargs["user_id"] = 1
        kwargs["channel"] = "Test Channel"

    # TODO fix this once these data are collected correctly
    kwargs["change_reason"] = "cause we can"

    serializer.is_valid(raise_exception=True)
    serializer.save()
