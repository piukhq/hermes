from typing import TYPE_CHECKING

import arrow

from payment_card.enums import RequestMethod
from payment_card.models import PaymentCard
from payment_card.tasks import metis_request

if TYPE_CHECKING:
    from payment_card.models import PaymentCardAccount


def _generate_card_json(account: 'PaymentCardAccount') -> dict:
    return {
        'payment_token': account.psp_token,
        'card_token': account.token,
        'partner_slug': account.payment_card.slug,
        'id': account.id,
        'date': arrow.get(account.created).timestamp
    }


def enrol_new_payment_card(account: 'PaymentCardAccount', run_async: bool = True) -> None:
    args = (
        RequestMethod.POST,
        '/payment_service/payment_card',
        _generate_card_json(account)
    )
    if run_async:
        metis_request.delay(*args)
    else:
        metis_request(*args)


def update_payment_card(account: 'PaymentCardAccount', run_async: bool = True) -> None:
    args = (
        RequestMethod.POST,
        '/payment_service/payment_card/update',
        _generate_card_json(account)
    )
    if run_async:
        metis_request.delay(*args)
    else:
        metis_request(*args)


def delete_payment_card(account: 'PaymentCardAccount', run_async: bool = True) -> None:
    args = (
        RequestMethod.DELETE,
        '/payment_service/payment_card',
        _generate_card_json(account)
    )
    if run_async:
        metis_request.delay(*args)
    else:
        metis_request(*args)


def enrol_existing_payment_card(account: 'PaymentCardAccount', run_async: bool = True) -> None:
    provider = account.payment_card.system

    if provider in [PaymentCard.VISA, PaymentCard.AMEX]:
        enrol_new_payment_card(account, run_async)
    elif provider == PaymentCard.MASTERCARD:
        update_payment_card(account, run_async)
    else:
        raise ValueError(f"Provider {provider} not found to enrol existing card")
