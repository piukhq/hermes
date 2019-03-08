from celery import shared_task

from scheme.mixins import BaseLinkMixin
from scheme.models import SchemeAccount
from scheme.serializers import LinkSchemeSerializer
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
