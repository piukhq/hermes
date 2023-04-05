from scheme.models import JourneyTypes
from ubiquity.models import AccountLinkStatus, SchemeAccountEntry


def do_refresh_balance(entry):
    sact_entry = SchemeAccountEntry.objects.get(id=entry.data["schemeaccountentry_id"])
    sact_entry.scheme_account.get_balance(journey=JourneyTypes.UPDATE, scheme_account_entry=sact_entry)
    return True


def do_mark_as_unknown(entry):
    sact_entry = SchemeAccountEntry.objects.get(id=entry.data["schemeaccountentry_id"])
    sact_entry.link_status = AccountLinkStatus.UNKNOWN_ERROR
    sact_entry.save(update_fields=["link_status"])
    return True
