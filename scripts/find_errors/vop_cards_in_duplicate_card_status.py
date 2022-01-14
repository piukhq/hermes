from payment_card.models import PaymentCard, PaymentCardAccount

from .base_script import BaseScript, Correction


class FindVOPCardsInDuplicateCardStatus(BaseScript):

    """Finds all VOP Activations where the status is set to 'activating', and then added to results log. Correction is
    set for each to try activation again. Script also checks for an equivalent active link in the PaymentSchemeEntry
    model, to check that activation should be retried. If one is not found then this action is blocked."""

    def script(self):
        duplicate_cards = PaymentCardAccount.objects.filter(
            status=PaymentCardAccount.DUPLICATE_CARD, payment_card__system=PaymentCard.VISA
        )

        for card in duplicate_cards:
            self.set_correction(Correction.SET_ACC_TO_ACTIVE)

            self.result.append(
                f"Payment Card Account ID: {card.id}, "
                f"Payment Status: {card.status_name}, "
                f"Correction: {self.correction_title}"
            )

            self.found += 1

            data = {
                "card_id": card.id,
            }

            self.make_correction(unique_id_string=f"{card.id}", data=data)
