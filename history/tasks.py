from celery import shared_task

from history.serializers import get_historical_serializer


@shared_task
def record_history(model_name: str, **kwargs) -> None:
    serializer = get_historical_serializer(model_name)(data=kwargs)
    serializer.is_valid(raise_exception=True)
    serializer.save()
