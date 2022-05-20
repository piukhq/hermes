from enum import IntEnum, auto

from .find_errors.barclays_hash_corrections_upload import BarclaysHashCorrectionsUpload
from .find_errors.cards_stuck_in_pending import FindCardsStuckInPending
from .find_errors.deleted_vop_cards_with_activations import FindDeletedVopCardsWithActivations
from .find_errors.scheme_accounts_invalid_creds import FindSchemeAccountsStuckInInvalidCreds
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
    SCHEMEACCOUNT_INVALIDCREDS = auto()
    BARCLAYS_HASH_UPLOAD = auto()


SCRIPT_TITLES = {
    DataScripts.METIS_CALLBACK: "Metis Callback (results container)",
    DataScripts.DEL_VOP_WITH_ACT: "Deleted VOP cards with remaining activations",
    DataScripts.ADD_MISSING_ACTIVATIONS: "VOP Card/scheme pairs with missing activation",
    DataScripts.REPEAT_VOP_ENROL_STUCK_CARDS: "Cards stuck in pending may need removing and re-adding",
    DataScripts.FIX_STUCK_IN_ACTIVATING: "VOP Activations stuck in activating",
    DataScripts.FIX_STUCK_IN_DEACTIVATING: "VOP Activations stuck in deactivating",
    DataScripts.VISA_DUPLICATE_CARDS: "Visa card accounts in 'duplicate card' status",
    DataScripts.SCHEMEACCOUNT_INVALIDCREDS: "SchemeAccounts stuck in Invalid Credentials status",
    DataScripts.BARCLAYS_HASH_UPLOAD: "Barclays hash replacement using Azure upload files",
}

SCRIPT_CLASSES = {
    DataScripts.DEL_VOP_WITH_ACT: FindDeletedVopCardsWithActivations,
    DataScripts.ADD_MISSING_ACTIVATIONS: FindVopCardsNeedingActivation,
    DataScripts.REPEAT_VOP_ENROL_STUCK_CARDS: FindCardsStuckInPending,
    DataScripts.FIX_STUCK_IN_ACTIVATING: FindVOPActivationsStuckInActivating,
    DataScripts.FIX_STUCK_IN_DEACTIVATING: FindVOPActivationsStuckInDeactivating,
    DataScripts.VISA_DUPLICATE_CARDS: FindVOPCardsInDuplicateCardStatus,
    DataScripts.SCHEMEACCOUNT_INVALIDCREDS: FindSchemeAccountsStuckInInvalidCreds,
    DataScripts.BARCLAYS_HASH_UPLOAD: BarclaysHashCorrectionsUpload,
}
# End of new script definition - you do not need to do anything else to add a new find script
# But you may need to add one or more corrective actions see models and admin actions
