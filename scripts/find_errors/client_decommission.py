from scripts.actions.corrections import Correction
from scripts.find_errors.base_script import BaseScript
from user.models import CustomUser


class FindUsersByClientBase(BaseScript):
    """
    This script is part of decommissioning a client.

    This will find all users (optionally excluding test users) for the given client in order to execute
    the deletion process for each.
    """

    client_name = "N/A"
    exclude_test_users = False

    def script(self):
        filters = {"client__name__iexact": self.client_name}
        if self.exclude_test_users:
            filters |= {
                "is_staff": False,
                "is_tester": False,
            }

        users_ids: list[int] = CustomUser.objects.values_list("id", flat=True).filter(**filters)
        for user_id in users_ids:
            self.set_correction(Correction.DELETE_CLIENT_USERS)
            self.make_correction(unique_id_string=f"{user_id!s}.{self.client_name}", data={"user_id": user_id})
            self.result.append(f"user_id: {user_id} " f"script:{self.correction_title}")


class FindBinkNonTestUsers(FindUsersByClientBase):
    """
    This script is part of decommissioning a the Bink client.

    This will find all non test users for the Bink client in order to execute the deletion process for each.
    """

    client_name = "bink"
    exclude_test_users = True


class FindBarclaysUsers(FindUsersByClientBase):
    """
    This script is part of decommissioning a the Barclays client.

    This will find all users for the Barclays client in order to execute the deletion process for each.
    """

    client_name = "Barclays Mobile Banking"
    exclude_test_users = False
