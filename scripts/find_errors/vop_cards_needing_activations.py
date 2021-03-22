from .base_script import BaseScript, Correction
from ubiquity.models import PaymentCardSchemeEntry, VopActivation


class FindVopCardsNeedingActivation(BaseScript):

    """Finds every record in PaymentCardSchemeEntry linked to an active visa cards (with active link).
    Then loops through each of these records, and checks that for each of these there is a corresponding VOP Activation
    entry. If this cannot be found, then card and scheme details are added to the results log, and correction is set to
    reactivate."""

    def script(self):
        # All active VISA cards
        active_visa_links = PaymentCardSchemeEntry.objects.filter(
            payment_card_account__payment_card__slug='visa', active_link=True
        )

        for link in active_visa_links:
            scheme = link.scheme_account.scheme
            pca = link.payment_card_account
            self.set_correction(Correction.ACTIVATE)

            vop_object = VopActivation.objects.filter(payment_card_account=pca.id, scheme=scheme.id)
            if vop_object.count() >= 1:
                pass
            elif vop_object.count() == 0:

                self.result.append(
                    f"payment card id: {pca.id}, "
                    f"payment card token: {pca.psp_token},"
                    f"scheme id: {scheme.id}, "
                    f"scheme slug: {scheme.slug}"
                    f"correction: {self.correction_title}"
                )

                self.found += 1

                data = {
                    'card_id': pca.id,
                    'scheme_id': scheme.id,
                    'scheme_slug': scheme.slug,
                    'payment_token': pca.psp_token
                }

                self.make_correction(
                    unique_id_string=f"{scheme.id}.{pca.id}", data=data
                )

