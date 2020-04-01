import typing as t

import requests
from celery import shared_task
from django.conf import settings
from rest_framework import serializers

from scheme.mixins import BaseLinkMixin, SchemeAccountJoinMixin
from scheme.models import SchemeAccount
from scheme.serializers import LinkSchemeSerializer
from ubiquity.models import SchemeAccountEntry
from user.models import CustomUser

if t.TYPE_CHECKING:
    from rest_framework.serializers import Serializer


def _send_metrics_to_atlas(method: str, slug: str, payload: dict) -> None:
    headers = {'Authorization': f'Token {settings.SERVICE_API_KEY}', 'Content-Type': 'application/json'}
    requests.request(method, f'{settings.ATLAS_URL}/audit/metrics/{slug}', data=payload, headers=headers)


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
def async_join(scheme_account_id: int, user_id: int, serializer: 'Serializer', scheme_id: int,
               validated_data: dict) -> None:
    user = CustomUser.objects.get(id=user_id)
    scheme_account = SchemeAccount.objects.get(id=scheme_account_id)

    SchemeAccountJoinMixin().handle_join_request(validated_data, user, scheme_id, scheme_account, serializer)


@shared_task
def async_registration(user_id: int, serializer: 'Serializer', scheme_account_id: int,
                       validated_data: dict) -> None:
    user = CustomUser.objects.get(id=user_id)
    scheme_account = SchemeAccount.objects.get(id=scheme_account_id)

    SchemeAccountJoinMixin().handle_join_request(validated_data, user, scheme_account.scheme_id,
                                                 scheme_account, serializer)


@shared_task
def async_join_journey_fetch_balance_and_update_status(scheme_account_id: int) -> None:
    scheme_account = SchemeAccount.objects.get(id=scheme_account_id)
    scheme_account.status = scheme_account.PENDING
    scheme_account.save(update_fields=['status'])
    scheme_account.get_cached_balance()


def _format_info(scheme_account: SchemeAccount, user_id: int) -> dict:
    consents = scheme_account.userconsent_set.filter(user_id=user_id).all()
    return {
        'card_number': scheme_account.card_number,
        'link_date': scheme_account.link_date,
        'consents': [
            {
                'text': c.metadata['text'],
                'answer': c.value
            }
            for c in consents
        ]
    }


@shared_task
def send_merchant_metrics_for_new_account(user_id: int, scheme_account_id: int, scheme_slug: str) -> None:
    scheme_account = SchemeAccount.objects.get(pk=scheme_account_id)
    consents = scheme_account.userconsent_set.filter(user_id=user_id).all()
    payload = {
        'scheme_account_id': scheme_account_id,
        'card_number': scheme_account.card_number,
        'link_date': scheme_account.link_date,
        'consents': [
            {
                'text': c.metadata['text'],
                'answer': c.value
            }
            for c in consents
        ]
    }
    if not payload['link_date']:
        del payload['link_date']

    _send_metrics_to_atlas('POST', scheme_slug, payload)


@shared_task
def send_merchant_metrics_for_link_delete(scheme_account_id: int, scheme_slug: str, date: str, date_type: str) -> None:
    if date_type not in ('link', 'delete'):
        raise ValueError(f'{date_type} in an invalid merchant metrics date_type')

    payload = {
        'scheme_account_id': scheme_account_id,
        f'{date_type}_date': date
    }
    _send_metrics_to_atlas('PATCH', scheme_slug, payload)
