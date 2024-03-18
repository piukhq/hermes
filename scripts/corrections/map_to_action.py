from scripts.actions.paymentaccount_actions import (
    do_orphaned_payment_card_cleanup,
    do_re_enroll,
    do_remove_payment_account,
    do_retain,
    do_un_enroll,
    do_update_hash,
)
from scripts.actions.rtbf_actions import do_right_to_be_forgotten
from scripts.actions.schemeaccount_actions import do_mark_as_unknown, do_refresh_balance
from scripts.actions.ubiquity_actions import (
    do_channel_retailer_offboarding,
    do_client_decommission,
    do_delete_user_cleanup,
    do_set_account_and_links_active,
    do_update_active_link_to_false,
)
from scripts.actions.vop_actions import (
    do_activation,
    do_deactivate,
    do_fix_enroll,
    do_mark_as_deactivated,
    do_multiple_deactivate_unenroll,
)
from scripts.corrections import Correction

MAPPED_ACTIONS = {
    Correction.VOP_UN_ENROLL: do_un_enroll,
    Correction.VOP_DEACTIVATE: do_deactivate,
    Correction.VOP_RE_ENROLL: do_re_enroll,
    Correction.VOP_ACTIVATE: do_activation,
    Correction.VOP_MARK_AS_DEACTIVATED: do_mark_as_deactivated,
    Correction.VOP_MULTIPLE_DEACTIVATE_UN_ENROLL: do_multiple_deactivate_unenroll,
    Correction.VOP_FIX_ENROLL: do_fix_enroll,
    Correction.RETAIN: do_retain,
    Correction.SET_ACTIVE: do_set_account_and_links_active,
    Correction.MARK_AS_UNKNOWN: do_mark_as_unknown,
    Correction.REFRESH_BALANCE: do_refresh_balance,
    Correction.UPDATE_CARD_HASH: do_update_hash,
    Correction.REMOVE_PAYMENT_ACCOUNT: do_remove_payment_account,
    Correction.UN_ENROLL_CARD: do_un_enroll,
    Correction.RE_ENROLL_CARD: do_re_enroll,
    Correction.UPDATE_ACTIVE_LINK: do_update_active_link_to_false,
    Correction.DELETE_CARD_LINKS_FOR_DELETED_USERS: do_delete_user_cleanup,
    Correction.DELETE_CLIENT_USERS: do_client_decommission,
    Correction.CHANNELS_RETAILER_OFFBOARDING: do_channel_retailer_offboarding,
    Correction.ORPHANED_PAYMENT_CARD_CLEANUP: do_orphaned_payment_card_cleanup,
    Correction.RTBF: do_right_to_be_forgotten,
}


def apply_mapped_action(entry: object):
    if hasattr(entry, "apply"):
        if entry.apply not in MAPPED_ACTIONS:
            return False
        return MAPPED_ACTIONS[entry.apply](entry)
    else:
        if entry.correction not in MAPPED_ACTIONS:
            return False

        return MAPPED_ACTIONS[entry.correction](entry)
