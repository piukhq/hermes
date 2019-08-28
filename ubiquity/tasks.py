import typing as t

from celery import shared_task

from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from scheme.mixins import BaseLinkMixin, SchemeAccountJoinMixin
from scheme.models import SchemeAccount
from scheme.serializers import LinkSchemeSerializer
from ubiquity.models import SchemeAccountEntry
from user.models import CustomUser

if t.TYPE_CHECKING:
    from hermes.channels import Permit


@shared_task
def async_link(auth_fields: dict, scheme_account_id: int, user_id: int) -> None:
    scheme_account = SchemeAccount.objects.get(id=scheme_account_id)
    user = CustomUser.objects.get(id=user_id)
    try:
        serializer = LinkSchemeSerializer(data=auth_fields, context={'scheme_account': scheme_account})
        BaseLinkMixin.link_account(serializer, scheme_account, user)
    except serializers.ValidationError as e:
        scheme_account.status = scheme_account.INVALID_CREDENTIALS
        scheme_account.save()
        raise e


@shared_task
def async_balance(instance_id: int) -> None:
    scheme_account = SchemeAccount.objects.get(id=instance_id)
    scheme_account.get_cached_balance()


@shared_task
def async_all_balance(user_id: int, channels_permit) -> None:
    query = {
        'user': user_id,
        'scheme_account__is_deleted': False
    }
    exclude_query = {'scheme_account__status__in': SchemeAccount.EXCLUDE_BALANCE_STATUSES}
    entries = channels_permit.related_model_query(SchemeAccountEntry.objects.filter(**query),
                                                  'scheme_account__scheme__'
                                                  )
    entries = entries.exclude(**exclude_query)

    for entry in entries:
        async_balance.delay(entry.scheme_account_id)


@shared_task
def async_join(scheme_account_id: int, user_id: int, permit: object, scheme_id: int, enrol_fields: dict) -> None:
    user = CustomUser.objects.get(id=user_id)
    scheme_account = SchemeAccount.objects.get(id=scheme_account_id)
    join_data = {
        'order': 0,
        **enrol_fields,
        'save_user_information': 'false',
        'scheme_account': scheme_account
    }

    try:
        SchemeAccountJoinMixin().handle_join_request(join_data, user, scheme_id, permit)
    except ValidationError:
        scheme_account.status = SchemeAccount.JOIN
        scheme_account.save()


@shared_task
def async_registration(user_id: int, permit: 'Permit', scheme_account_id: int, registration_fields: dict) -> None:
    user = CustomUser.objects.get(id=user_id)
    scheme_account = SchemeAccount.objects.get(id=scheme_account_id)

    manual_answer = scheme_account.card_number_answer
    main_credential = manual_answer if manual_answer else scheme_account.barcode_answer

    registration_data = {
        main_credential.question.type: main_credential.answer,
        'order': 0,
        **registration_fields,
        'save_user_information': 'false',
        'scheme_account': scheme_account
    }
    try:
        SchemeAccountJoinMixin().handle_join_request(registration_data, user,
                                                     scheme_account.scheme_id, permit)
    except ValidationError:
        scheme_account.status = SchemeAccount.PRE_REGISTERED_CARD
        scheme_account.save()
