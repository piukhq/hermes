from typing import TYPE_CHECKING

import arrow
from payment_card.enums import RequestMethod
from payment_card.models import PaymentCard
from payment_card.tasks import metis_request

if TYPE_CHECKING:
    from payment_card.models import PaymentCardAccount


def _generate_card_json(account: 'PaymentCardAccount', retry_id: int = -1) -> dict:
    data = {
        'payment_token': account.psp_token,
        'card_token': account.token,
        'partner_slug': account.payment_card.slug,
        'id': account.id,
        'date': arrow.get(account.created).timestamp
    }

    if retry_id > -1:
        data['retry_id'] = retry_id
    return data


def enrol_new_payment_card(account: 'PaymentCardAccount', run_async: bool = True, retry_id: int = -1) -> None:
    args = (
        RequestMethod.POST,
        '/payment_service/payment_card',
        _generate_card_json(account, retry_id)
    )
    if run_async:
        metis_request.delay(*args)
    else:
        metis_request(*args)


def update_payment_card(account: 'PaymentCardAccount', run_async: bool = True, retry_id: int = -1) -> None:
    args = (
        RequestMethod.POST,
        '/payment_service/payment_card/update',
        _generate_card_json(account, retry_id)
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


def retry_enrol(data):
    retry_obj = data["periodic_retry_obj"]
    retry_enrol_existing_payment_card(account_id=data['context']['card_id'], retry_id=retry_obj.id)


def retry_enrol_existing_payment_card(account_id: int, run_async: bool = True, retry_id: int = -1) -> None:
    account = PaymentCardAccount.objects.get(id=account_id)
    enrol_existing_payment_card(account, run_async, retry_id)


def enrol_existing_payment_card(account: 'PaymentCardAccount', run_async: bool = True, retry_id: int = -1) -> None:
    provider = account.payment_card.system

    if provider in [PaymentCard.VISA, PaymentCard.AMEX]:
        enrol_new_payment_card(account, run_async, retry_id)
    elif provider == PaymentCard.MASTERCARD:
        update_payment_card(account, run_async, retry_id)
    else:
        raise ValueError(f"Provider {provider} not found to enrol existing card")
