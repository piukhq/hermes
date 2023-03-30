from ubiquity.models import AccountLinkStatus, SchemeAccountEntry

from ..actions.corrections import Correction
from .base_script import BaseScript


class FindSchemeAccountsStuckInInvalidCreds(BaseScript):
    def script(self):
        scheme_account_entries = SchemeAccountEntry.objects.filter(link_status=AccountLinkStatus.INVALID_CREDENTIALS)

        for entry in scheme_account_entries:
            self.set_correction(Correction.MARK_AS_UNKNOWN)
            self.make_correction(unique_id_string=f"{str(entry.id)}", data={"schemeaccountentry_id": entry.id})
            self.result.append(
                f"schemeaccountentry_id: {entry.id} - schemeaccount_id: {entry.scheme_account_id} - "
                f"script:{self.correction_title}"
            )
