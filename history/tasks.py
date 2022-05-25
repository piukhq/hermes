from celery import shared_task

from history.data_warehouse import add_auth_outcome, auth_outcome, history_event, join_outcome, register_outcome
from history.models import get_historical_model
from history.serializers import get_historical_serializer


@shared_task
def record_history(model_name: str, **kwargs) -> None:
    serializer = get_historical_serializer(model_name)(data=kwargs)
    serializer.is_valid(raise_exception=True)
    history_event(model_name, serializer.validated_data)
    serializer.save()


@shared_task
def join_outcome_event(success: bool, scheme_account: object) -> None:
    from ubiquity.models import SchemeAccountEntry

    wallets = SchemeAccountEntry.objects.filter(scheme_account=scheme_account).all()
    for wallet in wallets:
        join_outcome(success, wallet.user, scheme_account)


@shared_task
def add_auth_outcome_event(success: bool, scheme_account: object) -> None:
    from ubiquity.models import SchemeAccountEntry

    wallets = SchemeAccountEntry.objects.filter(scheme_account=scheme_account).all()
    for wallet in wallets:
        add_auth_outcome(success, wallet.user, scheme_account)

@shared_task
def auth_outcome_event(success: bool, scheme_account: object) -> None:
    from ubiquity.models import SchemeAccountEntry

    wallets = SchemeAccountEntry.objects.filter(scheme_account=scheme_account).all()
    for wallet in wallets:
        auth_outcome(success, wallet.user, scheme_account)


@shared_task
def register_outcome_event(success: bool, scheme_account: object) -> None:
    from ubiquity.models import SchemeAccountEntry

    wallets = SchemeAccountEntry.objects.filter(scheme_account=scheme_account).all()
    for wallet in wallets:
        register_outcome(success, wallet.user, scheme_account)


@shared_task
def bulk_record_history(model_name: str, data_list: list) -> None:
    serializer = get_historical_serializer(model_name)(data=data_list, many=True)
    serializer.is_valid(raise_exception=True)
    model = get_historical_model(model_name)
    history_entries = []
    for data in serializer.validated_data:
        history_entries.append(model(**data))

    model.objects.bulk_create(history_entries, batch_size=100)
