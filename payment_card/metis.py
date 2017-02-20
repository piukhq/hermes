import requests
import arrow

from django.conf import settings


def enrol_payment_card(account):
    requests.post(settings.METIS_URL + '/payment_service/payment_card', json={
        'payment_token': account.psp_token,
        'card_token': account.token,
        'partner_slug': account.payment_card.slug,
        'id': account.id,
        'date': arrow.get(account.created).timestamp}, headers={
        'Authorization': 'Token {}'.format(settings.SERVICE_API_KEY),
        'Content-Type': 'application/json'})
