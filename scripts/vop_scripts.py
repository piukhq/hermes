from ubiquity.models import VopActivation
from scripts.models import ScriptResult
from payment_card.models import PaymentCardAccount


def find_deleted_vop_cards_with_activations(script_id, script_name):
    activations = VopActivation.objects.filter(status=VopActivation.ACTIVATED)
    status_names = dict(VopActivation.VOP_STATUS)
    correction_titles = dict(ScriptResult.CORRECTION_SCRIPTS)
    result = []
    correction_count = 0
    new_corrections = 0
    found = 0

    try:
        for a in activations:
            if a.payment_card_account.is_deleted:
                # When we have found a deleted card which has an activation record in the ACTIVATED state
                # we should probably deactivate it by  Enroll, Deactivate and Unenroll
                # However, we should not do this if another undeleted active card exists with the same token
                # So we start by looking for cards having the same token which share an activation since we use
                # objects manager it won't find the deleted card so we don't expect any to be found.
                # But if we do find an active card and it has an identical activation we don't want to deactivate it
                # instead just mark the card with this activation as deactivated

                duplicated_card_tokens = PaymentCardAccount.objects.filter(psp_token=a.payment_card_account.psp_token,
                                                                           status=PaymentCardAccount.ACTIVE)
                duplicate_activations = False

                dup_card_id = None
                correction = ScriptResult.DEACTIVATE_UN_ENROLLED
                for dup in duplicated_card_tokens:
                    dup_card_id = dup.id
                    dup_active = VopActivation.objects.filter(payment_card_account=dup,
                                                              scheme=a.scheme,
                                                              status=VopActivation.ACTIVATED)
                    if dup_active:
                        duplicate_activations = True
                        correction = ScriptResult.MARK_AS_DEACTIVATED
                        break

                result.append(f"activation: {a.id},{status_names[a.status]}, "
                              f"payment card id: {a.payment_card_account.id}, "
                              f"scheme {a.scheme}, "
                              f"deleted: {a.payment_card_account.is_deleted}, token: {a.payment_card_account.psp_token}"
                              f", other activations: {duplicate_activations}"
                              f", duplicated_card_id: {dup_card_id}, correction: {correction_titles[correction]}")
                found += 1
                if correction == ScriptResult.DEACTIVATE_UN_ENROLLED:
                    sequence = [ScriptResult.RE_ENROLL, ScriptResult.DEACTIVATE, ScriptResult.UN_ENROLL]
                else:
                    sequence = [correction]

                data = {
                    'script_id': script_id,
                    'activation': a.id,
                    'card_id': a.payment_card_account.id,
                    'payment_token': a.payment_card_account.psp_token,
                    'card_token': a.payment_card_account.token,
                    'partner_slug': a.payment_card_account.payment_card.slug,
                    'scheme_id': a.scheme.id,
                    'activation_id': a.activation_id,
                    'sequence': sequence,
                    'sequence_pos': 0,
                }

                ref = f"{a.id}.{a.payment_card_account.id}.{script_id}"
                sr, created = ScriptResult.objects.get_or_create(
                    item_id=ref, script_name=script_name,
                    defaults={
                        'data': data,
                        'apply': sequence[0],
                        'correction': correction
                    }
                )
                correction_count += 1
                if created:
                    new_corrections += 1

        summary = f"Found {found} Issues and added {new_corrections} correction_count"

    except BaseException as e:
        summary = f"Exception {e}"

    return summary, correction_count, "<br/>".join(result)
