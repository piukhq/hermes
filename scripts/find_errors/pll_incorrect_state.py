from django.db.models import Q

from scripts.actions.corrections import Correction
from scripts.find_errors.base_script import BaseScript
from ubiquity.models import PaymentCardSchemeEntry, PllUserAssociation, WalletPLLStatus


class FindIncorrectPLL(BaseScript):
    """Find any pll link that should be False either due to the payment card or scheme account entry
    status not active for all wallets

    Resolve by setting the current active_link state.
    """

    def script(self):
        incorrect_pll = []

        active_pll = PaymentCardSchemeEntry.objects.filter(active_link=True)

        for pll in active_pll:
            """
            Get list of user plls associated with the active base link.
            Check if user plls state and if all are not in active state base link needs to be set to False
            """
            user_pll = PllUserAssociation.objects.filter(pll=pll)
            if user_pll and user_pll.filter(
                Q(state=WalletPLLStatus.INACTIVE) | Q(state=WalletPLLStatus.PENDING)
            ).count() == len(user_pll):
                incorrect_pll.append(pll)

        for pll_obj in incorrect_pll:
            self.set_correction(Correction.UPDATE_ACTIVE_LINK)
            self.result.append(
                f"pll id: {pll_obj.id}, "
                f"pll payment card id: {pll_obj.payment_card_account}, "
                f"pll scheme account id: {pll_obj.scheme_account_id}, "
            )
            self.make_correction(unique_id_string=f"{pll_obj.id}", data={"paymentcardschemeentry_id": pll_obj.id})

            self.found += 1
