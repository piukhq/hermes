from enum import IntEnum, auto

from .find_errors.barclays_hash_uploads import BarclaysDeleteUpload, BarclaysHashCorrectionsUpload
from .find_errors.cards_in_provider_server_down_unknown import (
    FindAmexCardsInProviderServerDownUnknownStatus,
    FindMastercardCardsInProviderServerDownUnknownStatus,
    FindVOPCardsInProviderServerDownUnknownStatus,
)
from .find_errors.cards_stuck_in_pending import FindCardsStuckInPending
from .find_errors.deleted_users_with_links import FindDeletedUsersWithCardLinks
from .find_errors.deleted_vop_cards_with_activations import FindDeletedVopCardsWithActivations
from .find_errors.pll_incorrect_state import FindIncorrectPLL
from .find_errors.scheme_accounts_invalid_creds import FindIcelandSchemeAccountsStuckInInvalidCreds
from .find_errors.vop_activations_stuck_in_activating import FindVOPActivationsStuckInActivating
from .find_errors.vop_activations_stuck_in_deactivating import FindVOPActivationsStuckInDeactivating
from .find_errors.vop_cards_in_duplicate_card_status import FindVOPCardsInDuplicateCardStatus
from .find_errors.vop_cards_needing_activations import FindVopCardsNeedingActivation

# New scripts which find records to correct should be imported above and mapped in script functions
# Define name and title here.  Only Scripts names in SCRIPT_CLASSES will have a link on /admin/scripts/ page


class DataScripts(IntEnum):
    METIS_CALLBACK = auto()  # This is a placeholder in scripts results for call back data and not a real script
    DEL_VOP_WITH_ACT = auto()
    ADD_MISSING_ACTIVATIONS = auto()
    REPEAT_VOP_ENROL_STUCK_CARDS = auto()
    FIX_STUCK_IN_ACTIVATING = auto()
    FIX_STUCK_IN_DEACTIVATING = auto()
    VISA_DUPLICATE_CARDS = auto()
    VISA_PSD_UNKNOWN_CARDS = auto()
    ICELAND_SCHEME_ACCOUNT_INVALID_CREDS = auto()
    BARCLAYS_HASH_UPLOAD = auto()
    DELETE_LISTED_PAYMENT_ACCOUNTS = auto()
    FIX_FALSE_ACTIVE_PLL_LINK = auto()
    DELETED_USERS_WITH_CARD_LINKS = auto()
    AMEX_PSD_UNKNOWN_CARDS = auto()
    MASTERCARD_PSD_UNKNOWN_CARDS = auto()


# Titles displayed in Django Admin. Should make sense in the format "Find records for: [SCRIPT TITLE]"
SCRIPT_TITLES = {
    DataScripts.METIS_CALLBACK: "Metis Callback (results container)",
    DataScripts.DEL_VOP_WITH_ACT: "Deleted VOP cards with remaining activations",
    DataScripts.ADD_MISSING_ACTIVATIONS: "VOP Card/scheme pairs with missing activation",
    DataScripts.REPEAT_VOP_ENROL_STUCK_CARDS: "Cards stuck in pending may need removing and re-adding",
    DataScripts.FIX_STUCK_IN_ACTIVATING: "VOP Activations stuck in activating",
    DataScripts.FIX_STUCK_IN_DEACTIVATING: "VOP Activations stuck in deactivating",
    DataScripts.VISA_DUPLICATE_CARDS: "Visa card accounts in 'duplicate card' status",
    DataScripts.VISA_PSD_UNKNOWN_CARDS: "Visa card accounts in 'provider server down' or 'unknown' status",
    DataScripts.AMEX_PSD_UNKNOWN_CARDS: ("AMEX card accounts in 'provider server down' or 'unknown' status"),
    DataScripts.MASTERCARD_PSD_UNKNOWN_CARDS: (
        "Mastercard card accounts in 'provider server down' or 'unknown' status"
    ),
    DataScripts.ICELAND_SCHEME_ACCOUNT_INVALID_CREDS: (
        "Iceland SchemeAccounts added via Join stuck in Invalid Credentials status"
    ),
    DataScripts.BARCLAYS_HASH_UPLOAD: "Barclays hash replacement using Azure upload files",
    DataScripts.DELETE_LISTED_PAYMENT_ACCOUNTS: "Remove Payment Accounts in supplied CSV File",
    DataScripts.FIX_FALSE_ACTIVE_PLL_LINK: "Update PLL links that are marked incorrectly as True",
    DataScripts.DELETED_USERS_WITH_CARD_LINKS: "Deleted Users with Loyalty/Payment card links",
}

SCRIPT_CLASSES = {
    DataScripts.DEL_VOP_WITH_ACT: FindDeletedVopCardsWithActivations,
    DataScripts.ADD_MISSING_ACTIVATIONS: FindVopCardsNeedingActivation,
    DataScripts.REPEAT_VOP_ENROL_STUCK_CARDS: FindCardsStuckInPending,
    DataScripts.FIX_STUCK_IN_ACTIVATING: FindVOPActivationsStuckInActivating,
    DataScripts.FIX_STUCK_IN_DEACTIVATING: FindVOPActivationsStuckInDeactivating,
    DataScripts.VISA_DUPLICATE_CARDS: FindVOPCardsInDuplicateCardStatus,
    DataScripts.VISA_PSD_UNKNOWN_CARDS: FindVOPCardsInProviderServerDownUnknownStatus,
    DataScripts.AMEX_PSD_UNKNOWN_CARDS: FindAmexCardsInProviderServerDownUnknownStatus,
    DataScripts.MASTERCARD_PSD_UNKNOWN_CARDS: FindMastercardCardsInProviderServerDownUnknownStatus,
    DataScripts.ICELAND_SCHEME_ACCOUNT_INVALID_CREDS: FindIcelandSchemeAccountsStuckInInvalidCreds,
    DataScripts.BARCLAYS_HASH_UPLOAD: BarclaysHashCorrectionsUpload,
    DataScripts.DELETE_LISTED_PAYMENT_ACCOUNTS: BarclaysDeleteUpload,
    DataScripts.FIX_FALSE_ACTIVE_PLL_LINK: FindIncorrectPLL,
    DataScripts.DELETED_USERS_WITH_CARD_LINKS: FindDeletedUsersWithCardLinks,
}
# End of new script definition - you do not need to do anything else to add a new find script
# But you may need to add one or more corrective actions see actions/corrections.py
