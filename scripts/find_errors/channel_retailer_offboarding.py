from django.db import connection

from scripts.actions.corrections import Correction
from scripts.find_errors.base_script import BaseScript


class _FindRetailerAndChannelMembershipCards(BaseScript):
    """
    This script is part of decommissioning a ratailer for a specific channel.

    This will find all scheme accounts for the given retailer and channel in order to execute the offboarding process
    for each.

    This class needs to be inherited from to specify the desired scheme_slug and channel.
    """

    scheme_slug = "N/A"
    channels = []

    def _get_scheme_account_id_and_channels_map(self) -> str:
        """
        Example response structure:
        ```python
        [
            (
                SchemeAccount.id,
                {
                    ClientApplication.client_id: {
                        "id": ClientApplicationBundle.id,
                        "channel": ClientApplicationBundle.bundle_id,
                    }
                },
            ),
            ...,
        ]
        ```
        """

        params = [self.scheme_slug]
        sql = """
            SELECT
                sa.id,
                json_object_agg(
                    cab.client_id ,
                    json_build_object(
                        'id',
                        cab.id::TEXT,
                        'channel',
                        cab.bundle_id
                    )
                )
            FROM scheme_schemeaccount sa
            JOIN scheme_scheme s ON sa.scheme_id = s.id
            JOIN ubiquity_schemeaccountentry sae ON sa.id = sae.scheme_account_id
            JOIN "user" u ON sae.user_id = u.id
            JOIN user_clientapplication ca ON u.client_id = ca.client_id
            JOIN user_clientapplicationbundle cab ON ca.client_id = cab.client_id
            WHERE s.slug = %s
            AND sa.is_deleted = false
        """
        if self.channels:
            params.append(tuple(self.channels))
            sql += "\n AND cab.bundle_id IN %s"

        sql += "\n GROUP BY sa.id;"

        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            res = cursor.fetchall()

        return res

    def script(self):
        for scheme_account_id, client_channel_map in self._get_scheme_account_id_and_channels_map():
            self.set_correction(Correction.CHANNELS_RETAILER_OFFBOARDING)
            channels_ids = [v["id"] for v in client_channel_map.values()]
            self.make_correction(
                unique_id_string=(f"{scheme_account_id!s}.{self.scheme_slug}.[{','.join(channels_ids)}]"),
                data={"scheme_account_id": scheme_account_id, "client_channel_map": client_channel_map},
            )
            self.result.append(f"scheme_account_id: {scheme_account_id} " f"script:{self.correction_title}")


class FindBarclaysBinkWasabiMembershipCards(_FindRetailerAndChannelMembershipCards):
    scheme_slug = "wasabi-club"
    channels = ["com.barclays.bmb", "com.wasabi.bink.web"]


class FindBarclaysViatorMembershipCards(_FindRetailerAndChannelMembershipCards):
    scheme_slug = "bpl-viator"
    channels = ["com.barclays.bmb"]


class FindAllChannelsIcelandMembershipCards(_FindRetailerAndChannelMembershipCards):
    scheme_slug = "iceland-bonus-card"


class FindBarclaysSquaremealMembershipCards(_FindRetailerAndChannelMembershipCards):
    scheme_slug = "squaremeal"
    channels = ["com.barclays.bmb"]
