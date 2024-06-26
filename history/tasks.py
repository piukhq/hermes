import typing
from enum import Enum

from celery import shared_task

from history.data_warehouse import add_auth_outcome, auth_outcome, history_event, join_outcome, register_outcome
from history.enums import HistoryModel
from history.models import HistoricalBase, HistoricalCustomUser, get_historical_model
from history.serializers import get_historical_serializer

if typing.TYPE_CHECKING:
    from ubiquity.models import SchemeAccountEntry


@shared_task
def record_history(model_name: str, headers: dict | None = None, **kwargs) -> None:
    # Django is able to convert enums to the value before saving to the db but the serializer below will
    # raise an error for any enums. This is to convert to the value so no errors are raised, without having
    # to add .value to the enums in the code.
    for key, val in kwargs.items():
        if isinstance(val, Enum):
            kwargs[key] = val.value

    serializer = get_historical_serializer(model_name)(data=kwargs)
    serializer.is_valid(raise_exception=True)
    # Todo: Angelia is sending the model name without the app name
    #  i.e CustomUser but the following is expecting user.CustomUser
    if model_name == HistoryModel.CUSTOM_USER.value:
        if HistoricalCustomUser.objects.filter(
            instance_id=kwargs["instance"], change_type=HistoricalBase.CREATE
        ).exists():
            # Do nothing if create object is already there
            pass
    else:
        history_event(model_name, serializer.validated_data, headers=headers)
        serializer.save()


@shared_task
def join_outcome_event(success: bool, scheme_account_entry: "SchemeAccountEntry", headers: dict | None = None) -> None:
    join_outcome(success, scheme_account_entry, headers=headers)


@shared_task
def add_auth_outcome_task(
    success: bool,
    scheme_account_entry: "SchemeAccountEntry",
    date_time: object | None = None,
    headers: dict | None = None,
) -> None:
    add_auth_outcome(success, scheme_account_entry, date_time, headers=headers)


@shared_task
def auth_outcome_task(
    success: bool,
    scheme_account_entry: "SchemeAccountEntry",
    date_time: object | None = None,
    headers: dict | None = None,
) -> None:
    auth_outcome(success, scheme_account_entry, date_time, headers=headers)


@shared_task
def register_outcome_event(
    success: bool, scheme_account_entry: "SchemeAccountEntry", headers: dict | None = None
) -> None:
    register_outcome(success, scheme_account_entry, headers=headers)


@shared_task
def bulk_record_history(model_name: str, data_list: list) -> None:
    serializer = get_historical_serializer(model_name)(data=data_list, many=True)
    serializer.is_valid(raise_exception=True)
    model = get_historical_model(model_name)
    history_entries = []
    for data in serializer.validated_data:
        history_entries.append(model(**data))

    model.objects.bulk_create(history_entries, batch_size=100)
