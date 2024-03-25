import arrow

from payment_card.enums import RequestMethod
from payment_card.models import PaymentCard, PaymentCardAccount
from payment_card.tasks import metis_delete_cards_and_activations, metis_request
from periodic_retry.models import PeriodicRetry, PeriodicRetryStatus
from ubiquity.models import VopActivation


def _generate_card_json(account: "PaymentCardAccount", retry_id: int = -1) -> dict:
    data = {
        "payment_token": account.psp_token,
        "card_token": account.token,
        "partner_slug": account.payment_card.slug,
        "id": account.id,
        "date": arrow.get(account.created).int_timestamp,
    }

    if retry_id > -1:
        data["retry_id"] = retry_id
    return data


def enrol_new_payment_card(
    account: "PaymentCardAccount", run_async: bool = True, retry_id: int = -1, headers: dict | None = None
) -> None:
    args = (RequestMethod.POST, "/payment_service/payment_card", _generate_card_json(account, retry_id), headers)
    if run_async:
        metis_request.delay(*args)
    else:
        metis_request(*args)


def update_payment_card(
    account: "PaymentCardAccount", run_async: bool = True, retry_id: int = -1, headers: dict | None = None
) -> None:
    args = (RequestMethod.POST, "/payment_service/payment_card/update", _generate_card_json(account, retry_id), headers)
    if run_async:
        metis_request.delay(*args)
    else:
        metis_request(*args)


def delete_payment_card(
    account: "PaymentCardAccount",
    run_async: bool = True,
    retry_id: int = -1,
    status: object = VopActivation.ACTIVATED,
    headers: dict | None = None,
) -> None:
    url = "/payment_service/payment_card"
    payload = _generate_card_json(account, retry_id)
    if run_async:
        metis_delete_cards_and_activations.delay(RequestMethod.DELETE, url, payload, status, headers)
    else:
        metis_delete_cards_and_activations(RequestMethod.DELETE, url, payload, status, headers)


def retry_delete_payment_card(data):
    # Metis card check ensures retry callbacks are from delete retry providers eg VOP
    retry_obj = data["periodic_retry_obj"]
    account = PaymentCardAccount.all_objects.get(id=data["context"]["card_id"])
    delete_payment_card(account, retry_id=retry_obj.id, status=VopActivation.DEACTIVATING)


def retry_enrol(data):
    retry_obj: PeriodicRetry = data["periodic_retry_obj"]
    card_id = data["context"]["card_id"]
    try:
        account = PaymentCardAccount.objects.get(id=card_id)
        enrol_existing_payment_card(account, run_async=True, retry_id=retry_obj.id)
    except PaymentCardAccount.DoesNotExist:
        retry_obj.results += [f"PaymentCardAccount (id={card_id}) does not exist or has been deleted"]
        retry_obj.status = PeriodicRetryStatus.FAILED
        retry_obj.save(update_fields=["results", "status"])


def enrol_existing_payment_card(
    account: "PaymentCardAccount", run_async: bool = True, retry_id: int = -1, headers: dict | None = None
) -> None:
    provider = account.payment_card.system

    if provider in [PaymentCard.VISA, PaymentCard.AMEX]:
        enrol_new_payment_card(account, run_async, retry_id, headers)
    elif provider == PaymentCard.MASTERCARD:
        update_payment_card(account, run_async, retry_id, headers)
    else:
        raise ValueError(f"Provider {provider} not found to enrol existing card")
