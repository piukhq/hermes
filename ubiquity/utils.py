from collections.abc import Iterable

from django.conf import settings

from history.utils import history_bulk_update
from ubiquity.models import VopActivation


def needs_decryption(values: Iterable) -> bool:
    return all(isinstance(x, str) and len(x) > settings.ENCRYPTED_VALUES_LENGTH_CONTROL for x in values)


def vop_deactivation_dict_by_payment_card_id(payment_card_account_id, status=VopActivation.ACTIVATED):
    """Find activations matching account id and return a serializable object"""
    activation_dict = {}
    activations = VopActivation.objects.filter(payment_card_account_id=payment_card_account_id, status=status)
    update_activations = status != VopActivation.DEACTIVATING

    for activation in activations:
        activation_id = activation.activation_id
        activation_dict[activation.id] = {"scheme": activation.scheme.slug, "activation_id": activation_id}
        if update_activations:
            activation.status = VopActivation.DEACTIVATING

    if update_activations:
        history_bulk_update(VopActivation, activations, update_fields=["status"])

    return activation_dict
