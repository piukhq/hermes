from ubiquity.models import PllUserAssociation, WalletPLLStatus

from ..actions.corrections import Correction
from .base_script import BaseScript


class FindIncorrectPLL(BaseScript):

    """Find any pll link that should be False either due to the payment card or scheme account entry
    status not active

    Resolve by setting the current active_link state.
    """

    def script(self):
        incorrect_pll_records = PllUserAssociation.objects.select_related("pll").filter(
            state=WalletPLLStatus.INACTIVE,
            pll__active_link=True,
        )

        for pll_obj in incorrect_pll_records:
            self.set_correction(Correction.UPDATE_ACTIVE_LINK)
            self.result.append(
                f"pll user association id: {pll_obj.id} "
                f"pll user association state: {pll_obj.state} "
                f"pll id: {pll_obj.pll_id}, "
                f"pll active_link: {pll_obj.pll.active_link}, "
                f"pll scheme account id: {pll_obj.pll.scheme_account_id}, "
            )
            self.make_correction(
                unique_id_string=f"{pll_obj.pll_id}", data={"paymentcardschemeentry_id": pll_obj.pll_id}
            )

            self.found += 1
