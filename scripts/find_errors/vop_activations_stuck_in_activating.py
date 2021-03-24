from base_script import BaseScript
from ubiquity.models import VopActivation, PaymentCardSchemeEntry
from scripts.models import Correction
from scheme.models import SchemeAccount


class FindVOPActivationsStuckInActivating(BaseScript):

    """Finds all VOP Activations where the status is set to 'activating', and then added to results log. Correction is
    set for each to try activation again. Script also checks for an equivalent active link in the PaymentSchemeEntry
    model, to provide extra information, in case the activation should not be retried."""

    def script(self):
        activating = VopActivation.objects.filter(status=VopActivation.ACTIVATING)
        self.set_correction(Correction.ACTIVATE)

        for a in activating:
            pca = a.payment_card_account
            scheme = a.scheme
            scheme_account = SchemeAccount.objects.filter(scheme=scheme).get()

            active_link_check = PaymentCardSchemeEntry.objects.filter(scheme_account=scheme_account,
                                                                      payment_card_account=pca)

            if active_link_check.count >= 1:
                active_link = True
            else:
                active_link = False

            self.result.append(
                f"Activation ID: {a.id}, "
                f"Payment Card ID: {pca.id}, "
                f"Scheme ID: {scheme.id}, "
                f"Scheme Slug: {scheme.slug}, "
                f"Activation Status: {a.status}, "
                f"Activation ID: {a.activation_id}, "
                f"Correction: {self.correction_title}, "
                f"Has_active_link: {active_link}"
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
                unique_id_string="{a.id}.{pca.id}",
                data=data
            )
