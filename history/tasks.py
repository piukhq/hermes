from celery import shared_task

from history.models import get_historical_model
from history.serializers import get_historical_serializer


@shared_task
def record_history(model_name: str, **kwargs) -> None:
    serializer = get_historical_serializer(model_name)(data=kwargs)
    serializer.is_valid(raise_exception=True)
    serializer.save()


@shared_task
def bulk_record_history(model_name: str, data_list: list) -> None:
    serializer = get_historical_serializer(model_name)(data=data_list, many=True)
    serializer.is_valid(raise_exception=True)
    model = get_historical_model(model_name)
    history_entries = []
    for data in serializer.validated_data:
        history_entries.append(
            model(**data)
        )

    model.objects.bulk_create(history_entries, batch_size=100)
