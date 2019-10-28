from enum import Enum
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.admin.models import LogEntry
from django.conf import settings
from scheme.models import (Scheme, SchemeBundleAssociation, SchemeAccount, SchemeImage, Consent,
                           UserConsent, Control, SchemeDetail, ThirdPartyConsentLink)
from payment_card.models import PaymentCardAccount
from user.models import ClientApplicationBundle
from ubiquity.models import MembershipPlanDocument, PaymentCardAccountEntry, SchemeAccountEntry


class Actions(Enum):
    ADDITION = "admin_add"
    CHANGE = "admin_change"
    DELETE = "admin_delete"
    UNKNOWN = "admin_unknown"


class Collections(Enum):
    SCHEME = 'membership_plan'
    SCHEME_ACCOUNT = 'membership_card'
    PAYMENT_ACCOUNT = 'payment_card'


def lookup_action(flag: int):
    # flag meaning: 1 =  addition, 2 = change, 3 = Delete
    if flag == 1:
        return Actions.ADDITION
    elif flag == 2:
        return Actions.CHANGE
    elif flag == 3:
        return Actions.DELETE
    else:
        return Actions.UNKNOWN


def lookup_collection(model: str):
    if model == "scheme":
        return Collections.SCHEME
    elif model == "schemeaccount":
        return Collections.SCHEME_ACCOUNT
    elif model == "paymentcardaccount":
        return Collections.PAYMENT_ACCOUNT
    return False


association_map = {
    'membershipplandocument': {
        'collection': Collections.SCHEME,
        'model': MembershipPlanDocument,
        'field': 'scheme_id'
    },
    'schemebundleassociation': {
        'collection': Collections.SCHEME,
        'model': SchemeBundleAssociation,
        'field': 'scheme_id'
    },
    'consent': {
        'collection': Collections.SCHEME,
        'model': Consent,
        'field': 'scheme_id'
    },
    'control': {
        'collection': Collections.SCHEME,
        'model': Control,
        'field': 'scheme_id'
    },
    'schemedetail': {
        'collection': Collections.SCHEME,
        'model': SchemeDetail,
        'field': 'scheme_id'
    },
    'schemeimage': {
        'collection': Collections.SCHEME,
        'model': SchemeImage,
        'field': 'scheme_id'
    },
    'thirdpartyconsentlink': {
        'collection': Collections.SCHEME,
        'model': ThirdPartyConsentLink,
        'field': 'scheme_id'
    },
    'userconsent': {
        'collection': Collections.SCHEME,
        'model': UserConsent,
        'field': 'scheme_id'
    },
    'schemeaccountentry': {
        'collection': Collections.PAYMENT_ACCOUNT,
        'model': SchemeAccount,
        'field': 'scheme_account_id'
    }
}


def make_service_list(users: list):
    service_list = []
    for u in users:
        external_id = u.user.external_id
        bundle_id = ClientApplicationBundle.objects.values_list('bundle_id', flat=True).get(client=u.user.client_id)
        service_key = {'bundle_id': bundle_id, 'external_id': external_id}
        service_list.append(service_key)
    return service_list


def notify_daedalus(action: Actions, collection: Collections, object_id: int):
    extra_info = {}
    if action is not Actions.DELETE:
        if collection == Collections.SCHEME:
            scheme = Scheme.objects.get(id=object_id)
            bundle_links = SchemeBundleAssociation.objects.filter(scheme=scheme)
            bundle_list = []
            for bundle_link in bundle_links:
                if bundle_link.status != SchemeBundleAssociation.INACTIVE:
                    bundle_list.append(bundle_link.bundle.bundle_id)
            extra_info['bundles'] = bundle_list

        elif collection == Collections.SCHEME_ACCOUNT:
            scheme_account = SchemeAccount.objects.get(id=object_id)
            extra_info['membership_plan_key'] = scheme_account.scheme_id
            users = SchemeAccountEntry.objects.filter(scheme_account=scheme_account)
            extra_info['services'] = make_service_list(users)

        elif collection == Collections.PAYMENT_ACCOUNT:
            payment_account = PaymentCardAccount.objects.get(id=object_id)
            extra_info['issuer_key'] = payment_account.issuer_id
            users = PaymentCardAccountEntry.objects.filter(payment_card_account=payment_account)
            extra_info['services'] = make_service_list(users)

    settings.TO_DAEDALUS.send({
        "type": action.value,
        "collection": collection.value,
        "id": str(object_id),
        "extra": extra_info,
    },
        headers={'X-content-type': 'application/json'}
    )


def notify_related(action: Actions, model_name: str, object_id: int):
    # Delete related cannot be determined as the record was destroyed
    if action is not Actions.DELETE:
        assoc = association_map.get(model_name)
        if assoc:
            get_fields = assoc['model'].objects.get(id=object_id)
            if get_fields:
                related_id = getattr(get_fields, assoc['field'])
                notify_daedalus(action, assoc['collection'], related_id)


@receiver(post_save, sender=LogEntry)
def watch_for_admin_updates(sender, **kwargs):
    instance = kwargs.get("instance")
    if instance and settings.ENABLE_DAEDALUS_MESSAGING:
        object_id = instance.object_id
        content_type = instance.content_type
        if content_type:
            action = lookup_action(instance.action_flag)
            collection = lookup_collection(content_type.model)
            if collection:
                notify_daedalus(action, collection, object_id)
            else:
                notify_related(action, content_type.model, object_id)
