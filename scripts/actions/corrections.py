from .paymentaccount_actions import do_remove_payment_account, do_update_hash
from .schemeaccount_actions import do_mark_as_unknown, do_refresh_balance
from .vop_actions import (
    do_activation,
    do_deactivate,
    do_fix_enroll,
    do_mark_as_deactivated,
    do_re_enroll,
    do_retain,
    do_set_account_and_links_active,
    do_un_enroll,
)


class Correction:
    NO_CORRECTION = 0
    # VOP corrections
    MARK_AS_DEACTIVATED = 1
    ACTIVATE = 2
    DEACTIVATE_UN_ENROLLED = 3
    RE_ENROLL = 4
    DEACTIVATE = 5
    UN_ENROLL = 6
    FIX_ENROLL = 7
    RETAIN = 8
    RETAIN_FIX_ENROLL = 9
    RETRY_ENROLL = 10
    SET_ACTIVE = 11
    # Scheme account corrections
    MARK_AS_UNKNOWN = 1001
    REFRESH_BALANCE = 1002
    # Payment account corrections
    UPDATE_CARD_HASH = 2001
    DELETED_LISTED_CARDS = 2002

    CORRECTION_SCRIPTS = (
        (NO_CORRECTION, "No correction available"),
        # VOP
        (MARK_AS_DEACTIVATED, "Mark as deactivated as same token is also active"),
        (ACTIVATE, "VOP Activate"),
        (DEACTIVATE_UN_ENROLLED, "Re-enrol, VOP Deactivate, Un-enroll"),
        (RE_ENROLL, "Re-enroll"),
        (DEACTIVATE, "VOP Deactivate"),
        (UN_ENROLL, "Un-enroll"),
        (FIX_ENROLL, "Fix-enroll"),
        (RETAIN, "Retain"),
        (RETAIN_FIX_ENROLL, "Retain, Fix-Enroll"),
        (RETRY_ENROLL, "Un-enroll, Re-Enroll, Set Active"),
        (SET_ACTIVE, "Set Active"),
        # Scheme Account
        (MARK_AS_UNKNOWN, "Mark as Unknown"),
        (REFRESH_BALANCE, "Refresh Balance"),
        # Payment Account
        (UPDATE_CARD_HASH, "Update Payment Card Hash"),
        (DELETED_LISTED_CARDS, "Delete listed Payment Card"),
    )

    COMPOUND_CORRECTION_SCRIPTS = {
        # VOP:
        DEACTIVATE_UN_ENROLLED: [RE_ENROLL, DEACTIVATE, UN_ENROLL],
        RETAIN_FIX_ENROLL: [RETAIN, FIX_ENROLL],
        RETRY_ENROLL: [UN_ENROLL, RE_ENROLL, SET_ACTIVE],
        # Scheme Account:
        MARK_AS_UNKNOWN: [MARK_AS_UNKNOWN, REFRESH_BALANCE],
        # Payment Account:
        # No compound scripts defined yet
    }

    TITLES = dict(CORRECTION_SCRIPTS)

    @classmethod
    def do(cls, entry: object):
        actions = {
            cls.UN_ENROLL: do_un_enroll,
            cls.DEACTIVATE: do_deactivate,
            cls.RE_ENROLL: do_re_enroll,
            cls.ACTIVATE: do_activation,
            cls.MARK_AS_DEACTIVATED: do_mark_as_deactivated,
            cls.FIX_ENROLL: do_fix_enroll,
            cls.RETAIN: do_retain,
            cls.SET_ACTIVE: do_set_account_and_links_active,
            cls.MARK_AS_UNKNOWN: do_mark_as_unknown,
            cls.REFRESH_BALANCE: do_refresh_balance,
            cls.UPDATE_CARD_HASH: do_update_hash,
            cls.DELETED_LISTED_CARDS: do_remove_payment_account,
        }
        if entry.apply not in actions.keys():
            return False
        return actions[entry.apply](entry)
