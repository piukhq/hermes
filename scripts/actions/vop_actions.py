from time import sleep

from django.conf import settings
from requests import request

from payment_card.enums import RequestMethod
from payment_card.metis import enrol_existing_payment_card
from payment_card.models import PaymentCardAccount
from scheme.models import Scheme
from ubiquity.models import VopActivation


class Correction:
    NO_CORRECTION = 0
    MARK_AS_DEACTIVATED = 1
    ACTIVATE = 2
    DEACTIVATE_UN_ENROLLED = 3
    RE_ENROLL = 4
    DEACTIVATE = 5
    UN_ENROLL = 6
    FIX_ENROLL = 7
    RETAIN = 8
    RETAIN_FIX_ENROLL = 9

    CORRECTION_SCRIPTS = (
        (NO_CORRECTION, 'No correction available'),
        (MARK_AS_DEACTIVATED, 'Mark as deactivated as same token is also active'),
        (ACTIVATE, 'VOP Activate'),
        (DEACTIVATE_UN_ENROLLED, 'Re-enrol, VOP Deactivate, Un-enroll'),
        (RE_ENROLL, 'Re-enroll'),
        (DEACTIVATE, 'VOP Deactivate'),
        (UN_ENROLL, 'Un-enroll'),
        (FIX_ENROLL, 'Fix-enroll'),
        (RETAIN, 'Retain'),
        (RETAIN_FIX_ENROLL, 'Retain, Fix-Enroll'),
    )

    COMPOUND_CORRECTION_SCRIPTS = {
        DEACTIVATE_UN_ENROLLED: [RE_ENROLL, DEACTIVATE, UN_ENROLL],
        RETAIN_FIX_ENROLL: [RETAIN, FIX_ENROLL]
    }


def metis_request(method: RequestMethod, endpoint: str, payload: dict) -> object:
    response = request(
        method.value,
        settings.METIS_URL + endpoint,
        json=payload,
        headers={
            'Authorization': 'Token {}'.format(settings.SERVICE_API_KEY),
            'Content-Type': 'application/json'
        }
    )
    return response.json()


def do_fix_enroll(entry):
    card = PaymentCardAccount.objects.get(id=entry.data['card_id'])
    enrol_existing_payment_card(card, False)
    for i in range(0, 10):
        acc = PaymentCardAccount.objects.get(id=entry.data['card_id'])
        if acc.status != PaymentCardAccount.PENDING:
            return True
        else:
            sleep(1)
    return False


def do_retain(entry):
    card = PaymentCardAccount.objects.get(id=entry.data['card_id'])
    data = {
        'payment_token': entry.data['payment_token'],
        'id': entry.data['card_id']
    }
    reply = metis_request(RequestMethod.POST, f'/foundation/spreedly/{card.payment_card.slug}/retain', data)
    if reply.get('status_code') == 200 and reply.get('reason') == 'OK':
        return True
    return False


def do_un_enroll(entry):
    data = {
        'payment_token': entry.data['payment_token'],
        'id': entry.data['card_id']
    }
    reply = metis_request(RequestMethod.POST, '/foundation/visa/remove', data)
    if reply.get('agent_response_code') == 'Delete:SUCCESS' and reply.get('status_code') == 201:
        return True
    return False


def do_deactivate(entry):
    data = {
        'payment_token': entry.data['payment_token'],
        'activation_id': entry.data['activation_id'],
        'id': entry.data['card_id']
    }
    reply = metis_request(RequestMethod.POST, '/visa/deactivate', data)
    if reply.get('agent_response_code') == 'Deactivate:SUCCESS':
        do_mark_as_deactivated(entry)
        return True
    return False


def do_re_enroll(entry):
    data = {
        'payment_token': entry.data['payment_token'],
        'card_token': entry.data['card_token'],
        'id': entry.data['card_id']
    }
    reply = metis_request(RequestMethod.POST, '/foundation/spreedly/visa/add', data)
    if reply.get('agent_response_code') == 'Add:SUCCESS' and reply.get('status_code') == 200:
        return True
    return False


def do_activation(entry):
    # Creates a VOPActivation object for the entry (if none exists already), before triggering a metis request to VOP
    # for activation.
    vop_activation, created = VopActivation.objects.get_or_create(
        payment_card_account=PaymentCardAccount.objects.get(id=entry.data['card_id']),
        scheme=Scheme.objects.get(id=entry.data['scheme_id']),
        defaults={'activation_id': "", "status": VopActivation.ACTIVATING}
    )

    if not entry.data.get('activation'):
        entry.data['activation'] = vop_activation.id
        entry.save(update_fields=['data'])

    data = {
        'payment_token': entry.data['payment_token'],
        'merchant_slug': entry.data['scheme_slug'],
        'id': entry.data['card_id']
    }

    reply = metis_request(RequestMethod.POST, '/visa/activate', data)
    if reply.get('agent_response_code') == 'Activate:SUCCESS':
        do_mark_as_activated(entry)
        return True
    return False


def do_mark_as_deactivated(entry):
    act = VopActivation.objects.get(id=entry.data['activation'])
    act.status = VopActivation.DEACTIVATED
    act.save(update_fields=['status'])
    return True


def do_mark_as_activated(entry):
    act = VopActivation.objects.get(id=entry.data['activation'])
    act.status = VopActivation.ACTIVATED
    act.save(update_fields=['status'])
    return True
