import typing as t

from celery import shared_task

from scheme.mixins import BaseLinkMixin, SchemeAccountJoinMixin
from scheme.models import SchemeAccount
from scheme.serializers import LinkSchemeSerializer
from ubiquity.models import SchemeAccountEntry
from user.models import CustomUser


@shared_task
def async_link(auth_fields: dict, scheme_account_id: int, user_id: int) -> None:
    scheme_account = SchemeAccount.objects.get(id=scheme_account_id)
    user = CustomUser.objects.get(id=user_id)
    serializer = LinkSchemeSerializer(data=auth_fields, context={'scheme_account': scheme_account})
    BaseLinkMixin.link_account(serializer, scheme_account, user)


@shared_task
def async_balance(instance_id: int) -> None:
    scheme_account = SchemeAccount.objects.get(id=instance_id)
    scheme_account.get_cached_balance()


@shared_task
def async_all_balance(user_id: int, allowed_schemes: t.Sequence[int] = None) -> None:
    query = {'user': user_id}
    if allowed_schemes:
        query['scheme_account__scheme__in'] = allowed_schemes

    entries = SchemeAccountEntry.objects.filter(**query)
    for entry in entries:
        async_balance.delay(entry.scheme_account_id)


@shared_task
def async_join(user_id: int, scheme_id: int, enrol_fields: dict) -> None:
    user = CustomUser.objects.get(id=user_id)
    join_data = {
        'order': 0,
        **enrol_fields,
        'save_user_information': 'false'
    }
    SchemeAccountJoinMixin().handle_join_request(join_data, user, scheme_id)


@shared_task
def async_registration(user_id: int, scheme_account_id: int, registration_fields: dict) -> None:
    user = CustomUser.objects.get(id=user_id)
    account = SchemeAccount.objects.get(id=scheme_account_id)

    manual_answer = account.card_number_answer
    main_credential = manual_answer if manual_answer else account.barcode_answer

    registration_data = {
        main_credential.question.type: main_credential.answer,
        'order': 0,
        **registration_fields,
        'save_user_information': False,
    }
    SchemeAccountJoinMixin().handle_join_request(registration_data, user, account.scheme_id)
