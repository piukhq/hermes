from .base_script import BaseScript
from ubiquity.models import VopActivation
from scripts.models import Correction


class FindVOPActivationsStuckInDeactivating(BaseScript):

    """Finds all VOP Activations where the status is set to 'deactivating', and then added to results log. Correction is
    set for each to try deactivation again."""

    def script(self):
        deactivating = VopActivation.objects.filter(status=VopActivation.DEACTIVATING)

        for d in deactivating:
            pcd = d.payment_card_account
            scheme = d.scheme
            self.set_correction(Correction.DEACTIVATE)

            self.result.append(
                f"Activation ID: {d.id}, "
                f"Payment Card ID: {pcd.id}, "
                f"Scheme ID: {scheme.id}, "
                f"Scheme Slug: {scheme.slug}, "
                f"Activation Status: {d.status}, "
                f"Activation ID: {d.activation_id}, "
                f"Correction: {self.correction_title}"
            )

            self.found += 1

            data = {
                'activation': d.id,
                'card_id': pcd.id,
                'payment_token': pcd.psp_token,
                'card_token': pcd.token,
                'scheme_id': scheme.id,
                'scheme_slug': scheme.slug,
                'partner_slug': pcd.payment_card.slug,
                'activation_id': d.activation_id,
            }

            self.make_correction(
                unique_id_string=f"{d.id}.{pcd.id}",
                data=data
            )