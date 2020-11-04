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
                # We have found a deleted card which should not have an activation
                # Three corrective actions are possible:
                #     1) Mark it as deactivated because another card with same token has an activation
                #     2) Transfer activation record to a card with same token
                #     3) deactivate Enroll, Deactivate and Unenroll

                duplicated_card_tokens = PaymentCardAccount.objects.filter(psp_token=a.payment_card_account.psp_token)
                duplicate_activations = False
                duplicate_without_activation = False
                dup_card_id = None
                correction = ScriptResult.DEACTIVATE_UN_ENROLLED
                for dup in duplicated_card_tokens:
                    duplicate_without_activation = True
                    correction = ScriptResult.TRANSFER_ACTIVATION
                    dup_card_id = dup.id
                    dup_active = VopActivation.objects.filter(payment_card_account=dup,
                                                              scheme=a.scheme,
                                                              status=VopActivation.ACTIVATED)
                    if dup_active:
                        duplicate_activations = True
                        duplicate_without_activation = False
                        correction = ScriptResult.MARK_AS_DEACTIVATED
                        break

                result.append(f"id: {a.id},{status_names[a.status]}, payment card id: {a.payment_card_account.id}, "
                              f"scheme {a.scheme},"
                              f"deleted: {a.payment_card_account.is_deleted}, token: {a.payment_card_account.psp_token}"
                              f", other activations: {duplicate_activations}, transfer: {duplicate_without_activation}"
                              f", duplicated_card_id: {dup_card_id}, correction: {correction_titles[correction]}")
                found += 1
                if correction == ScriptResult.DEACTIVATE_UN_ENROLLED:
                    sequence = [ScriptResult.RE_ENROLL, ScriptResult.DEACTIVATE, ScriptResult.UN_ENROLL]
                else:
                    sequence = [correction]

                data = {
                    'script_id': script_id,
                    'card_id': a.payment_card_account.id,
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

