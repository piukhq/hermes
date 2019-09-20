from enum import Enum
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.admin.models import LogEntry
from hermes.settings import TO_DAEDALUS, ENABLE_DAEDALUS_MESSAGING
from scheme.models import (Scheme, SchemeBundleAssociation, Exchange, SchemeAccount, SchemeImage, Category,
                           SchemeAccountCredentialAnswer, SchemeCredentialQuestion, SchemeAccountImage, Consent,
                           UserConsent, SchemeBalanceDetails, SchemeCredentialQuestionChoice,
                           SchemeCredentialQuestionChoiceValue, Control, SchemeDetail,
                           ThirdPartyConsentLink)
from ubiquity.models import PaymentCardSchemeEntry, MembershipPlanDocument

import json


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
    elif model == "paymentcardasaccount":
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
}


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

    TO_DAEDALUS.send({"type": action.value,
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
    if instance and ENABLE_DAEDALUS_MESSAGING:
        object_id = instance.object_id
        content_type = instance.content_type
        if content_type:
            action = lookup_action(instance.action_flag)
            collection = lookup_collection(content_type.model)
            if collection:
                notify_daedalus(action, collection, object_id)
            else:
                notify_related(action, content_type.model, object_id)