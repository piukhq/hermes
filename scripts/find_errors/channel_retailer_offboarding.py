from scheme.models import SchemeAccount

from ..actions.corrections import Correction
from .base_script import BaseScript


class _FindRetailerAndChannelMembershipCards(BaseScript):
    """
    This script is part of decommissioning a ratailer for a specific channel.

    This will find all scheme accounts for the given retailer and channel in order to execute the unboarding process
    for each.

    This class needs to be inherited from to specify the desired scheme_slug and channel.
    """

    scheme_slug: str = "N/A"
    channel: str | None = None

    def script(self):
        filter_params = {
            "scheme__slug__iexact": self.scheme_slug,
            "is_deleted": False,
        }
        if self.channel:
            filter_params["user_set__client__clientapplicationbundle__bundle_id"] = self.channel

        for scheme_account_id in SchemeAccount.objects.values_list("id", flat=True).filter(**filter_params):
            self.set_correction(Correction.CHANNEL_RETAILER_OFFBOARDING)
            self.make_correction(
                unique_id_string=f"{str(scheme_account_id)}.{self.scheme_slug}.{self.channel}",
                data={"scheme_account_id": scheme_account_id, "channel": self.channel},
            )
            self.result.append(f"scheme_account_id: {scheme_account_id} " f"script:{self.correction_title}")


class FindBarclaysWasabiMembershipCards(_FindRetailerAndChannelMembershipCards):
    scheme_slug = "wasabi-club"
