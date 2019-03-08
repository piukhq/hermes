from celery import shared_task

from scheme.mixins import BaseLinkMixin
from scheme.models import SchemeAccount
from scheme.serializers import LinkSchemeSerializer
from ubiquity.models import SchemeAccountEntry
from user.models import CustomUser


@shared_task
def async_link(auth_fields, scheme_account_id, user_id):
    scheme_account = SchemeAccount.objects.get(id=scheme_account_id)
    user = CustomUser.objects.get(id=user_id)
    serializer = LinkSchemeSerializer(data=auth_fields, context={'scheme_account': scheme_account})
    BaseLinkMixin.link_account(serializer, scheme_account, user)


@shared_task
def async_balance(instance_id):
    scheme_account = SchemeAccount.objects.get(id=instance_id)
    scheme_account.get_cached_balance()


@shared_task
def async_all_balance(user_id, allowed_schemes=None):
    query = {'user': user_id}
    if allowed_schemes:
        query['scheme_account__scheme__in'] = allowed_schemes

    entries = SchemeAccountEntry.objects.filter(**query)
    for entry in entries:
        async_balance.delay(entry.scheme_account_id)
