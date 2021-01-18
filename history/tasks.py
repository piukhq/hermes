from celery import shared_task

from history.serializers import get_history_serializer


@shared_task
def record_history(model_name: str, **kwargs) -> None:
    serializer = get_history_serializer[model_name](data=kwargs)
    serializer.is_valid(raise_exception=True)
    serializer.save()


@shared_task
def record_bulk_history(model_name: str, models_data: list) -> None:
    pass
