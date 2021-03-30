from .base_script import BaseScript, Correction
from ubiquity.models import VopActivation, PaymentCardSchemeEntry


class FindVOPActivationsStuckInActivating(BaseScript):

    """Finds all VOP Activations where the status is set to 'activating', and then added to results log. Correction is
    set for each to try activation again. Script also checks for an equivalent active link in the PaymentSchemeEntry
    model, to check that activation should be retried. If one is not found then this action is blocked."""

    def script(self):
        activating = VopActivation.objects.filter(status=VopActivation.ACTIVATING)

        for a in activating:
            pca = a.payment_card_account
            scheme = a.scheme
            active_link_check = PaymentCardSchemeEntry.objects.filter(scheme_account__scheme=scheme,
                                                                      payment_card_account=pca,
                                                                      active_link=True)
            if active_link_check.count() >= 1:
                active_link = True
            else:
                active_link = False

            active_link_str = 'True' if active_link else '*NO ACTIVE LINK FOUND!*'
            if active_link:
                self.set_correction(Correction.ACTIVATE)
            else:
                self.set_correction(Correction.NO_CORRECTION)

            self.result.append(
                f"Activation ID: {a.id}, "
                f"Payment Card ID: {pca.id}, "
                f"Scheme ID: {scheme.id}, "
                f"Scheme Slug: {scheme.slug}, "
                f"Activation Status: {a.status}, "
                f"Activation ID: {a.activation_id}, "
                f"Has_active_link: {active_link_str} >> "
                f"Correction: {self.correction_title}"
            )

            self.found += 1

            data = {
                'activation': a.id,
                'card_id': pca.id,
                'payment_token': pca.psp_token,
                'card_token': pca.token,
                'scheme_id': scheme.id,
                'scheme_slug': scheme.slug,
                'partner_slug': pca.payment_card.slug,
                'activation_id': a.activation_id,
                'has_active_link': active_link
            }

            self.make_correction(
                unique_id_string=f"{a.id}.{pca.id}",
                data=data
            )
