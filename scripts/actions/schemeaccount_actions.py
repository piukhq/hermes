from scheme.models import JourneyTypes, SchemeAccount


def do_refresh_balance(entry):
    sact = SchemeAccount.objects.get(id=entry.data["schemeaccount_id"])
    sact.get_midas_balance(JourneyTypes.UPDATE)
    sact.save(update_fields=["status"])
    return True


def do_mark_as_unknown(entry):
    sact = SchemeAccount.objects.get(id=entry.data["schemeaccount_id"])
    sact.status = SchemeAccount.UNKNOWN_ERROR
    sact.save(update_fields=["status"])
    return True
