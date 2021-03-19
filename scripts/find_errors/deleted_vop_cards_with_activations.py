from payment_card.models import PaymentCardAccount
from ubiquity.models import VopActivation
from ..models import Correction
from .base_script import BaseScript


class FindDeletedVopCardsWithActivations(BaseScript):

    def script(self):
        activations = VopActivation.objects.filter(status=VopActivation.ACTIVATED)
        status_names = dict(VopActivation.VOP_STATUS)

        for a in activations:
            if a.payment_card_account.is_deleted:
                # When we have found a deleted card which has an activation record in the ACTIVATED state
                # we should probably deactivate it by  Enroll, Deactivate and Unenroll
                # However, we should not do this if another undeleted active card exists with the same token
                # So we start by looking for cards having the same token which share an activation since we use
                # objects manager it won't find the deleted card so we don't expect any to be found.
                # But if we do find an active card and it has an identical activation we don't want to deactivate it
                # instead just mark the card with this activation as deactivated

                duplicated_card_tokens = PaymentCardAccount.objects.filter(
                    psp_token=a.payment_card_account.psp_token,
                    status=PaymentCardAccount.ACTIVE)
                duplicate_activations = False

                dup_card_id = None
                self.set_correction(Correction.DEACTIVATE_UN_ENROLLED)
                for dup in duplicated_card_tokens:
                    dup_card_id = dup.id
                    if dup.status == PaymentCardAccount.ACTIVE:
                        # we can't correct by re-enrolling because VOP should be enrolled still
                        # best try just activating
                        self.set_correction(Correction.DEACTIVATE)
                    dup_active = VopActivation.objects.filter(payment_card_account=dup,
                                                              scheme=a.scheme,
                                                              status=VopActivation.ACTIVATED)
                    if dup_active:
                        # This token and merchant are already activated on another card
                        # so safe to mark this deleted card as having been deactivated
                        duplicate_activations = True
                        self.set_correction(Correction.MARK_AS_DEACTIVATED)
                        break

                self.result.append(
                    f"activation: {a.id},{status_names[a.status]}, "
                    f"payment card id: {a.payment_card_account.id}, "
                    f"scheme {a.scheme}, "
                    f"deleted: {a.payment_card_account.is_deleted}, token: {a.payment_card_account.psp_token}"
                    f", other activations: {duplicate_activations}"
                    f", duplicated_card_id: {dup_card_id}, correction:"
                    f" {self.correction_title}"
                )
                self.found += 1

                self.make_correction(
                    f"{a.id}.{a.payment_card_account.id}",
                    {
                        'activation': a.id,
                        'card_id': a.payment_card_account.id,
                        'payment_token': a.payment_card_account.psp_token,
                        'card_token': a.payment_card_account.token,
                        'partner_slug': a.payment_card_account.payment_card.slug,
                        'scheme_id': a.scheme.id,
                        'scheme_slug': a.scheme.slug,
                        'activation_id': a.activation_id,
                    }
                )
