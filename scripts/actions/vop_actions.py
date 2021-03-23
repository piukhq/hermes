from django.conf import settings
from requests import request

from payment_card.enums import RequestMethod
from ubiquity.models import VopActivation
from payment_card.models import PaymentCardAccount
from scheme.models import Scheme


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

    if created:
        entry.data['activation'] = vop_activation.id

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

