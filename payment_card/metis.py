from hermes.traced_requests import requests
import arrow

from django.conf import settings


def _generate_card_json(account):
    return {
        'payment_token': account.psp_token,
        'card_token': account.token,
        'partner_slug': account.payment_card.slug,
        'id': account.id,
        'date': arrow.get(account.created).timestamp
    }


def enrol_new_payment_card(account):
    requests.post(settings.METIS_URL + '/payment_service/payment_card',
                  json=_generate_card_json(account),
                  headers={'Authorization': 'Token {}'.format(settings.SERVICE_API_KEY),
                           'Content-Type': 'application/json'})


def enrol_existing_payment_card(account):
    requests.post(settings.METIS_URL + '/payment_service/payment_card/update',
                  json=_generate_card_json(account),
                  headers={'Authorization': 'Token {}'.format(settings.SERVICE_API_KEY),
                           'Content-Type': 'application/json'})
