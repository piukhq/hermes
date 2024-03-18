from django.db.models import Count, Q

from scripts.corrections import Correction
from scripts.find_errors.base_script import BaseScript
from user.models import CustomUser


class FindDeletedUsersWithCardLinks(BaseScript):
    def script(self):
        users = CustomUser.all_objects.annotate(
            num_mcard_links=Count("schemeaccountentry"), num_pcard_links=Count("paymentcardaccountentry")
        ).filter(Q(is_active=False), Q(num_mcard_links__gt=0) | Q(num_pcard_links__gt=0))

        for user in users:
            self.set_correction(Correction.DELETE_CARD_LINKS_FOR_DELETED_USERS)
            self.make_correction(unique_id_string=str(user.id), data={"user_id": user.id})
            self.result.append(f"user_id:{user.id} script:{self.correction_title}")
