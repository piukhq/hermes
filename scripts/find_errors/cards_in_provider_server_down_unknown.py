from payment_card.models import PaymentCard, PaymentCardAccount
from scripts.actions.corrections import Correction
from scripts.find_errors.base_script import BaseScript


class BasePsdUnknown(BaseScript):
    def script(self):
        cards = PaymentCardAccount.objects.filter(
            status__in=(PaymentCardAccount.PROVIDER_SERVER_DOWN, PaymentCardAccount.UNKNOWN),
            payment_card__system=self.PAYMENT_CARD_SYSTEM,
            is_deleted=False,
        )

        for card in cards:
            self.set_correction(self.CORRECTION)

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


class FindAmexCardsInProviderServerDownUnknownStatus(BasePsdUnknown):
    """Finds all Mastercard Payment Card Accounts where the status == 'PROVIDER_SERVER_DOWN' or 'UNKNOWN, and sets
    the status to 'ACTIVE'. This is to allow for bulk fixes."""

    PAYMENT_CARD_SYSTEM = PaymentCard.AMEX
    CORRECTION = Correction.AMEX_RETRY_ENROL


class FindMastercardCardsInProviderServerDownUnknownStatus(BasePsdUnknown):
    """Finds all AMEX Payment Card Accounts where the status == 'PROVIDER_SERVER_DOWN' or 'UNKNOWN, and sets
    the status to 'ACTIVE'. This is to allow for bulk fixes."""

    PAYMENT_CARD_SYSTEM = PaymentCard.MASTERCARD
    CORRECTION = Correction.MC_RETRY_ENROL


class FindVOPCardsInProviderServerDownUnknownStatus(BasePsdUnknown):
    """Finds all Visa Payment Card Accounts where the status == 'PROVIDER_SERVER_DOWN' or 'UNKNOWN, and sets the status
    to 'ACTIVE'. This is to allow for bulk fixes."""

    PAYMENT_CARD_SYSTEM = PaymentCard.VISA
    CORRECTION = Correction.VOP_RETRY_ENROLL
