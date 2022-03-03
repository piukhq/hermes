from celery import shared_task

from history.data_warehouse import to_data_warehouse
from history.models import get_historical_model
from history.serializers import get_historical_serializer


@shared_task
def record_history(model_name: str, **kwargs) -> None:
    serializer = get_historical_serializer(model_name)(data=kwargs)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    body = data.get("body", {})
    if model_name == "CustomUser" and data.get("change_type") == "create":
        extra_data = {"external_id": body.get("external_id"), "email": body.get("email")}
        event_time_string = data["event_time"].strftime("%Y-%m-%d %H:%M:%S.%f")
        to_data_warehouse("event.user.created.api", body.get("id"), data.get("channel"), event_time_string, extra_data)
    serializer.save()


@shared_task
def bulk_record_history(model_name: str, data_list: list) -> None:
    serializer = get_historical_serializer(model_name)(data=data_list, many=True)
    serializer.is_valid(raise_exception=True)
    model = get_historical_model(model_name)
    history_entries = []
    for data in serializer.validated_data:
        history_entries.append(model(**data))

    model.objects.bulk_create(history_entries, batch_size=100)
