from django.db.models import Count

from payment_card.models import PaymentCardAccount
from scripts.actions.corrections import Correction
from scripts.find_errors.base_script import BaseScript


class FindOrphanedPaymentCards(BaseScript):
    """
    This script is part of cleaning up orphaned payment cards.
    """

    def script(self):
        orphaned_cards = (
            PaymentCardAccount.all_objects.values_list("id")
            .annotate(n_links=Count("paymentcardaccountentry__id"))
            .filter(is_deleted=False, n_links=0)
        )
        for card_id, *_ in orphaned_cards.all():
            self.set_correction(Correction.ORPHANED_PAYMENT_CARD_CLEANUP)
            self.make_correction(unique_id_string=str(card_id), data={"card_id": card_id})
            self.result.append(f"card_id: {card_id} " f"script:{self.correction_title}")
