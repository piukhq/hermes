from hermes.traced_requests import requests
import arrow

from django.conf import settings

from payment_card.models import PaymentCardAccount


def _generate_card_json(account):
    return {
        'payment_token': account.psp_token,
        'card_token': account.token,
        'partner_slug': account.payment_card.slug,
        'id': account.id,
        'date': arrow.get(account.created).timestamp,
        # TODO: Remove fingerprint from here and in the draft metis changes
        'fingerprint': account.fingerprint
    }


def enrol_new_payment_card(account):
    requests.post(settings.METIS_URL + '/payment_service/payment_card',
                  json=_generate_card_json(account),
                  headers={'Authorization': 'Token {}'.format(settings.SERVICE_API_KEY),
                           'Content-Type': 'application/json'})


def enrol_existing_payment_card(account):
    provider = account.payment_card.name

    if provider == 'visa' or 'amex':
        enrol_new_payment_card(account)

    elif provider == 'mastercard':
        requests.post(settings.METIS_URL + '/payment_service/payment_card/update',
                      json=_generate_card_json(account),
                      headers={'Authorization': 'Token {}'.format(settings.SERVICE_API_KEY),
                               'Content-Type': 'application/json'})


def delete_payment_card(account):
    requests.delete(settings.METIS_URL + '/payment_service/payment_card', json=_generate_card_json(account),
                    headers={'Authorization': 'Token {}'.format(settings.SERVICE_API_KEY),
                             'Content-Type': 'application/json'})
