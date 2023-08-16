from user.models import CustomUser

from ..actions.corrections import Correction
from .base_script import BaseScript


class FindClientNonTestUsers(BaseScript):
    """
    This script is part of decommissioning a client.

    This will find all non-test users for the given client in order to execute the deletion process
    for each.
    """

    def script(self):
        client_name = "bink"
        users_ids: list[int] = CustomUser.objects.values_list("id", flat=True).filter(
            client__name__iexact=client_name,
            is_staff=False,
            is_tester=False,
        )

        for user_id in users_ids:
            self.set_correction(Correction.DELETE_CLIENT_USERS)
            self.make_correction(unique_id_string=f"{str(user_id)}.{client_name}", data={"user_id": user_id})
            self.result.append(f"user_id: {user_id} " f"script:{self.correction_title}")
