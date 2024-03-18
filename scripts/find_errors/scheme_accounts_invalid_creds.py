from scripts.corrections import Correction
from scripts.find_errors.base_script import BaseScript
from ubiquity.models import AccountLinkStatus, SchemeAccountEntry


class FindIcelandSchemeAccountsStuckInInvalidCreds(BaseScript):
    """
    This script is to resolve issues with Iceland's batch Join process where an attempt to get balance immediately
    after a successful Join may result in a VALIDATION error from the Iceland balance endpoint. This ends up
    setting the account to an INVALID_CREDENTIALS status.

    Manually refreshing the balance for these accounts via this script can resolve the issue.
    """

    def script(self):
        scheme_account_entries = SchemeAccountEntry.objects.filter(
            scheme_account__scheme__slug="iceland-bonus-card",
            scheme_account__join_date__isnull=False,
            link_status=AccountLinkStatus.INVALID_CREDENTIALS,
        )

        for entry in scheme_account_entries:
            self.set_correction(Correction.MARK_AS_UNKNOWN)
            self.make_correction(unique_id_string=f"{entry.id!s}", data={"schemeaccountentry_id": entry.id})
            self.result.append(
                f"schemeaccountentry_id: {entry.id} - schemeaccount_id: {entry.scheme_account_id} - "
                f"script:{self.correction_title}"
            )
