import arrow

from payment_card.enums import RequestMethod
from payment_card.models import PaymentCard
from payment_card.tasks import async_metis_request


def _generate_card_json(account):
    return {
        'payment_token': account.psp_token,
        'card_token': account.token,
        'partner_slug': account.payment_card.slug,
        'id': account.id,
        'date': arrow.get(account.created).timestamp
    }


def enrol_new_payment_card(account):
    async_metis_request.delay(
        RequestMethod.POST,
        '/payment_service/payment_card',
        _generate_card_json(account)
    )


def update_payment_card(account):
    async_metis_request.delay(
        RequestMethod.POST,
        '/payment_service/payment_card/update',
        _generate_card_json(account)
    )


def delete_payment_card(account):
    async_metis_request.delay(
        RequestMethod.DELETE,
        '/payment_service/payment_card',
        _generate_card_json(account)
    )


def enrol_existing_payment_card(account):
    provider = account.payment_card.system

    if provider in [PaymentCard.VISA, PaymentCard.AMEX]:
        enrol_new_payment_card(account)
    elif provider == PaymentCard.MASTERCARD:
        update_payment_card(account)
    else:
        raise ValueError(f"Provider {provider} not found to enrol existing card")
