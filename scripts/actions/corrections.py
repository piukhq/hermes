from .paymentaccount_actions import (  # do_delete_payment_account,
    do_remove_payment_account,
    do_retain,
    do_un_enroll_card,
    do_update_hash,
)
from .schemeaccount_actions import do_mark_as_unknown, do_refresh_balance
from .vop_actions import (
    do_activation,
    do_deactivate,
    do_fix_enroll,
    do_mark_as_deactivated,
    do_multiple_deactivate_unenroll,
    do_re_enroll,
    do_set_account_and_links_active,
    do_vop_un_enroll,
)


class Correction:
    NO_CORRECTION = 0
    # VOP corrections
    VOP_MARK_AS_DEACTIVATED = 1
    VOP_ACTIVATE = 2
    VOP_DEACTIVATE_UN_ENROLLED = 3
    VOP_RE_ENROLL = 4
    VOP_DEACTIVATE = 5
    VOP_UN_ENROLL = 6
    VOP_FIX_ENROLL = 7
    RETAIN = 8
    VOP_RETAIN_FIX_ENROLL = 9
    VOP_RETRY_ENROLL = 10
    VOP_SET_ACTIVE = 11
    VOP_MULTIPLE_DEACTIVATE_UN_ENROLL = 12
    VOP_REMOVE_DEACTIVATE_AND_DELETE_PAYMENT_ACCOUNT = 13
    # Scheme account corrections
    MARK_AS_UNKNOWN = 1001
    REFRESH_BALANCE = 1002
    # Payment account corrections
    UPDATE_CARD_HASH = 2001
    REMOVE_PAYMENT_ACCOUNT = 2002
    DELETE_PAYMENT_ACCOUNT = 2003
    REMOVE_UN_ENROLL_DELETE_PAYMENT_ACCOUNT = 2004
    UN_ENROLL_CARD = 2005

    CORRECTION_SCRIPTS = (
        (NO_CORRECTION, "No correction available"),
        # VOP
        (VOP_MARK_AS_DEACTIVATED, "Mark as deactivated as same token is also active"),
        (VOP_ACTIVATE, "VOP Activate"),
        (VOP_DEACTIVATE_UN_ENROLLED, "Re-enrol, VOP Deactivate, VOP Un-enroll"),
        (VOP_RE_ENROLL, "VOP Re-enroll"),
        (VOP_DEACTIVATE, "VOP Deactivate"),
        (VOP_UN_ENROLL, "VOP Un-enroll"),
        (VOP_FIX_ENROLL, "VOP Fix-enroll"),
        (RETAIN, "Retain"),
        (VOP_RETAIN_FIX_ENROLL, "Retain, VOP Fix-Enroll"),
        (VOP_RETRY_ENROLL, "VOP Un-enroll, VOP Re-Enroll, VOP Set Active"),
        (VOP_SET_ACTIVE, "Set Active"),
        (VOP_MULTIPLE_DEACTIVATE_UN_ENROLL, "VOP Multiple Deactivate Unenrol"),
        (VOP_REMOVE_DEACTIVATE_AND_DELETE_PAYMENT_ACCOUNT, "Remove, Deactivate and unenrol,"),
        # Scheme Account
        (MARK_AS_UNKNOWN, "Mark as Unknown"),
        (REFRESH_BALANCE, "Refresh Balance"),
        # Payment Account
        (UPDATE_CARD_HASH, "Update Payment Card Hash"),
        (REMOVE_PAYMENT_ACCOUNT, "Remove Payment Card Account"),
        (DELETE_PAYMENT_ACCOUNT, "Delete Payment Card Account"),
        (REMOVE_UN_ENROLL_DELETE_PAYMENT_ACCOUNT, "Remove, Un_enroll, Delete Payment Card Account"),
        (UN_ENROLL_CARD, "UNENROLL Payment Card Account"),
    )

    COMPOUND_CORRECTION_SCRIPTS = {
        # VOP:
        VOP_DEACTIVATE_UN_ENROLLED: [VOP_RE_ENROLL, VOP_DEACTIVATE, VOP_UN_ENROLL],
        VOP_RETAIN_FIX_ENROLL: [RETAIN, VOP_FIX_ENROLL],
        VOP_RETRY_ENROLL: [VOP_UN_ENROLL, VOP_RE_ENROLL, VOP_SET_ACTIVE],
        # Scheme Account:
        MARK_AS_UNKNOWN: [MARK_AS_UNKNOWN, REFRESH_BALANCE],
        # Payment Account:
        REMOVE_UN_ENROLL_DELETE_PAYMENT_ACCOUNT: [REMOVE_PAYMENT_ACCOUNT, UN_ENROLL_CARD, DELETE_PAYMENT_ACCOUNT],
        VOP_REMOVE_DEACTIVATE_AND_DELETE_PAYMENT_ACCOUNT: [
            REMOVE_PAYMENT_ACCOUNT,
            VOP_MULTIPLE_DEACTIVATE_UN_ENROLL,
            DELETE_PAYMENT_ACCOUNT,
        ],
    }

    TITLES = dict(CORRECTION_SCRIPTS)

    @classmethod
    def do(cls, entry: object):
        actions = {
            cls.VOP_UN_ENROLL: do_vop_un_enroll,
            cls.VOP_DEACTIVATE: do_deactivate,
            cls.VOP_RE_ENROLL: do_re_enroll,
            cls.VOP_ACTIVATE: do_activation,
            cls.VOP_MARK_AS_DEACTIVATED: do_mark_as_deactivated,
            cls.VOP_MULTIPLE_DEACTIVATE_UN_ENROLL: do_multiple_deactivate_unenroll,
            cls.VOP_FIX_ENROLL: do_fix_enroll,
            cls.RETAIN: do_retain,
            cls.VOP_SET_ACTIVE: do_set_account_and_links_active,
            cls.MARK_AS_UNKNOWN: do_mark_as_unknown,
            cls.REFRESH_BALANCE: do_refresh_balance,
            cls.UPDATE_CARD_HASH: do_update_hash,
            cls.REMOVE_PAYMENT_ACCOUNT: do_remove_payment_account,
            cls.UN_ENROLL_CARD: do_un_enroll_card,
        }
        if entry.apply not in actions.keys():
            return False
        return actions[entry.apply](entry)