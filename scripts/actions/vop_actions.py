from time import sleep

from hermes.vop_tasks import activate
from payment_card.enums import RequestMethod
from payment_card.metis import enrol_existing_payment_card
from payment_card.models import PaymentCardAccount
from scheme.models import Scheme
from ubiquity.models import VopActivation

from .metis_foundation import metis_foundation_request
from .paymentaccount_actions import do_un_enroll


def do_fix_enroll(entry):
    """Does a full Metis enrol via the Payment Card endpoint in Metis, including a callback to Hermes which will change
    the status."""
    card = PaymentCardAccount.objects.get(id=entry.data["card_id"])
    enrol_existing_payment_card(card, False)
    for _ in range(0, 10):
        acc = PaymentCardAccount.objects.get(id=entry.data["card_id"])
        if acc.status != PaymentCardAccount.PENDING:
            return True
        else:
            sleep(1)
    return False


def do_deactivate(entry):
    data = {
        "payment_token": entry.data["payment_token"],
        "activation_id": entry.data["activation_id"],
        "id": entry.data["card_id"],
    }
    reply = metis_foundation_request(RequestMethod.POST, "/visa/deactivate", data)
    if reply.get("agent_response_code") == "Deactivate:SUCCESS":
        do_mark_as_deactivated(entry)
        return True
    return False


def do_activation(entry):
    # Creates a VOPActivation object for the entry (if none exists already), before triggering a metis request to VOP
    # for activation.
    vop_activation, created = VopActivation.objects.get_or_create(
        payment_card_account=PaymentCardAccount.objects.get(id=entry.data["card_id"]),
        scheme=Scheme.objects.get(id=entry.data["scheme_id"]),
        defaults={"activation_id": "", "status": VopActivation.ACTIVATING},
    )

    if not entry.data.get("activation"):
        entry.data["activation"] = vop_activation.id
        entry.save(update_fields=["data"])

    data = {
        "payment_token": entry.data["payment_token"],
        "payment_slug": "visa",
        "merchant_slug": entry.data["scheme_slug"],
        "id": entry.data["card_id"],
    }

    status, response = activate(vop_activation, data)
    if response.get("agent_response_code") == "Activate:SUCCESS":
        return True
    return False


def do_mark_as_deactivated(entry):
    act = VopActivation.objects.get(id=entry.data["activation"])
    act.status = VopActivation.DEACTIVATED
    act.save(update_fields=["status"])
    return True


def do_multiple_deactivate(entry: dict) -> bool:
    """Sets removes list of activations and sets each to deactivated if found.  This is not as controllable
    as doing one at a time so it will do best endeavours to deactivate but will return True in any case.
    That will not therefore block the next action or completion of the script.  This was first used for
    Barclays payment card delete where it was not so critical that an activation remains on a deleted card.
    Deactivations will only be marked on success so other scripts might be able to correct the situation"""
    deactivate_list = entry.get("deactivations")
    for deactivate in deactivate_list:
        do_deactivate(deactivate)

    return True


def do_multiple_deactivate_unenroll(entry: dict) -> bool:
    """Sets removes list of activations, setting each to deactivated if found. Then unenrols VOP card.
    This is not as controllable as doing each action one step at a time so it will do best endeavours to deactivate
    and will return True if unenrol exceeds or False if not.
    This was first used for Barclays payment card delete where it was not so critical that an activation remains on
    a deleted card.
    Deactivations will only be marked on success so other scripts might be able to correct any errors due to remaining
    activation. This will require using the scrip that enrols, removes activation and unerols"""
    deactivate_list = entry.get("deactivations")
    for deactivate in deactivate_list:
        do_deactivate(deactivate)
    return do_un_enroll(entry)
