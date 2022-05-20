from payment_card.models import PaymentCardAccount


class PaymentAccountCorrection:
    # note start at 2000 because scheme account is 1000
    # but may grow and these need to be unique
    UPDATE_CARD_HASH = 2001

    CORRECTION_SCRIPTS = ((UPDATE_CARD_HASH, "Update Card Hash"),)

    COMPOUND_CORRECTION_SCRIPTS = {}


def do_update_hash(entry):
    acc = PaymentCardAccount.objects.get(id=entry.data["payment_card_account_id"])
    acc.hash = entry.data["new_hash"]
    acc.save(update_fields=["hash", "updated"])
    return True
