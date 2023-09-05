from scheme.models import SchemeAccount
from user.models import ClientApplicationBundle

from ..actions.corrections import Correction
from .base_script import BaseScript


class _FindRetailerAndChannelMembershipCards(BaseScript):
    """
    This script is part of decommissioning a ratailer for a specific channel.

    This will find all scheme accounts for the given retailer and channel in order to execute the unboarding process
    for each.

    This class needs to be inherited from to specify the desired scheme_slug and channel.
    """

    scheme_slug = "N/A"
    channels = []

    def script(self):
        clients_to_bundle_map = dict(
            ClientApplicationBundle.objects.filter(bundle_id__in=self.channels).values_list(
                "client", "bundle_id", named=False
            )
        )

        scheme_accounts = SchemeAccount.objects.values_list("id", flat=True).filter(
            scheme__slug__iexact=self.scheme_slug,
            user_set__client_id__in=clients_to_bundle_map.keys(),
            is_deleted=False,
        )

        for scheme_account_id in scheme_accounts:
            self.set_correction(Correction.CHANNELS_RETAILER_OFFBOARDING)
            self.make_correction(
                unique_id_string=f"{str(scheme_account_id)}.{self.scheme_slug}.{'.'.join(self.channels)}",
                data={"scheme_account_id": scheme_account_id, "clients_to_bundle_map": clients_to_bundle_map},
            )
            self.result.append(f"scheme_account_id: {scheme_account_id} " f"script:{self.correction_title}")


class FindBarclaysBinkWasabiMembershipCards(_FindRetailerAndChannelMembershipCards):
    scheme_slug = "wasabi-club"
    channels = ["com.barclays.bmb", "com.wasabi.bink.web"]


class FindBarclaysViatorMembershipCards(_FindRetailerAndChannelMembershipCards):
    scheme_slug = "bpl-viator"
    channels = ["com.barclays.bmb"]
