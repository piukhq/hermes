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
    SET_ACTIVE = 11
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
    RE_ENROLL_CARD = 2006
    AMEX_RETRY_ENROL = 2007
    MC_RETRY_ENROL = 2008
    ORPHANED_PAYMENT_CARD_CLEANUP = 2009
    # PLL corrections
    UPDATE_ACTIVE_LINK = 3001
    # User corrections
    DELETE_CARD_LINKS_FOR_DELETED_USERS = 4001
    DELETE_CLIENT_USERS = 5001
    CHANNELS_RETAILER_OFFBOARDING = 6001
    RTBF = 7001

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
        (AMEX_RETRY_ENROL, "AMEX Un-enroll, AMEX Re-Enroll, AMEX Set Active"),
        (MC_RETRY_ENROL, "Mastercard Un-enroll, Mastercard Re-Enroll, Mastercard Set Active"),
        (SET_ACTIVE, "Set Active"),
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
        (UN_ENROLL_CARD, "UN-ENROLL Payment Card Account"),
        (RE_ENROLL_CARD, "RE-ENROLL Payment Card Account"),
        (UPDATE_ACTIVE_LINK, "Update PLL Active Link"),
        (ORPHANED_PAYMENT_CARD_CLEANUP, "Soft delete a payment card and send a un-enroll request to Metis"),
        # Users
        (DELETE_CARD_LINKS_FOR_DELETED_USERS, "Delete card links for deleted Users"),
        (DELETE_CLIENT_USERS, "Run delete process for Bink client users"),
        (CHANNELS_RETAILER_OFFBOARDING, "Offboard membership cards for specific retailer and channels"),
    )

    FILE_CORRECTION_SCRIPTS = (
        (NO_CORRECTION, "No correction available"),
        (RTBF, "Right to be forgotten"),
    )

    COMPOUND_CORRECTION_SCRIPTS = {
        # VOP:
        VOP_DEACTIVATE_UN_ENROLLED: [VOP_RE_ENROLL, VOP_DEACTIVATE, VOP_UN_ENROLL],
        VOP_RETAIN_FIX_ENROLL: [RETAIN, VOP_FIX_ENROLL],
        VOP_RETRY_ENROLL: [VOP_UN_ENROLL, VOP_RE_ENROLL, SET_ACTIVE],
        AMEX_RETRY_ENROL: [UN_ENROLL_CARD, RE_ENROLL_CARD, SET_ACTIVE],
        MC_RETRY_ENROL: [UN_ENROLL_CARD, RE_ENROLL_CARD, SET_ACTIVE],
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
