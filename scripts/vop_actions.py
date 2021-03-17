import arrow
from django.conf import settings
from requests import request
from ubiquity.models import VopActivation
from payment_card.enums import RequestMethod


def get_card_data(entry):
    return {
        'payment_token': entry.data['payment_token'],
        'card_token': entry.data['card_token'],
        'partner_slug': entry.data['partner_slug'],
        'id': 999,
        'date': arrow.utcnow().timestamp
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


def do_un_enroll(entry):
    data = {
        'payment_token': entry.data['payment_token'],
        'id': entry.data['card_id']
    }
    reply = metis_request(RequestMethod.POST, '/foundation/visa/remove', data)
    if reply.get('agent_error_code') == 'Delete:SUCCESS' and reply.get('status_code') == 201:
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
    if reply.get('agent_error_code') == 'Add:SUCCESS' and reply.get('status_code') == 200:
        return True
    return False


def do_transfer_activation(entry):
    return True


def do_mark_as_deactivated(entry):
    act = VopActivation.objects.get(id=entry.data['activation'])
    act.status = VopActivation.DEACTIVATED
    act.save(update_fields=['status'])
    return True
