from payment_card.models import PaymentCardAccount
from scripts.corrections import Correction
from scripts.find_errors.base_script import BaseScript


class FindCardsStuckInPending(BaseScript):
    def script(self):
        accounts = PaymentCardAccount.objects.filter(status=PaymentCardAccount.PENDING)
        for account in accounts:
            self.set_correction(Correction.VOP_RETAIN_FIX_ENROLL)
            self.make_correction(str(account.id), {"card_id": account.id, "payment_token": account.psp_token})
            self.result.append(f"card_id:{account.id}" f"script:{self.correction_title}" f"token: {account.psp_token}")
