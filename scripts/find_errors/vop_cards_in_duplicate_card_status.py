from payment_card.models import PaymentCard, PaymentCardAccount

from .base_script import BaseScript, Correction


class FindVOPCardsInDuplicateCardStatus(BaseScript):

    """Finds all Visa Payment Card Accounts where the status == 'DUPLICATE_CARD', and sets the status to 'ACTIVE'.
    This is to allow for bulk fixes in the case of outages or service issues which might erroneously cause duplicate
    cards to be reported in the system."""

    def script(self):
        duplicate_cards = PaymentCardAccount.objects.filter(
            status=PaymentCardAccount.DUPLICATE_CARD, payment_card__system=PaymentCard.VISA
        )

        for card in duplicate_cards:
            self.set_correction(Correction.RETRY_ENROLL)

            self.result.append(
                f"Payment Card Account ID: {card.id}, "
                f"Payment Status: {card.status_name}, "
                f"Correction: {self.correction_title}"
            )

            self.found += 1

            data = {
                "card_id": card.id,
                "payment_token": card.psp_token,
                "card_token": card.token,
                "partner_slug": card.payment_card.slug,
            }

            self.make_correction(unique_id_string=f"{card.id}", data=data)
