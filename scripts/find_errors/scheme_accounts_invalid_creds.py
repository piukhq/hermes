from scheme.models import SchemeAccount
from scripts.actions.schemeaccount_actions import SchemeAccountCorrection


from .base_script import BaseScript


class FindSchemeAccountsStuckInInvalidCreds(BaseScript):
    def script(self):
        scheme_accounts = SchemeAccount.objects.filter(status=SchemeAccount.INVALID_CREDENTIALS)
        for scheme_account in scheme_accounts[:10]: # just do 10 martin
            print(scheme_account.id)
            self.set_correction(SchemeAccountCorrection.MARK_AS_UNKNOWN)
            self.make_correction(str(scheme_account.id), {"schemeaccount_id": scheme_account.id})
            self.result.append(f"schemeaccount_id: {scheme_account.id}" f" script:{self.correction_title}")
