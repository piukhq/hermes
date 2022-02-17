from scheme.models import JourneyTypes, SchemeAccount


class SchemeAccountCorrection:
    # note start at 1000 because vop_actions end at 13 currently
    # but may grow and these need to be unique
    MARK_AS_UNKNOWN = 1001
    REFRESH_BALANCE = 1002

    CORRECTION_SCRIPTS = ((MARK_AS_UNKNOWN, "Mark as Unknown"), (REFRESH_BALANCE, "Refresh Balance"))

    COMPOUND_CORRECTION_SCRIPTS = {
        MARK_AS_UNKNOWN: [MARK_AS_UNKNOWN, REFRESH_BALANCE],
    }


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
