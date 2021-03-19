from enum import IntEnum, auto

from .find_errors.cards_stuck_in_pending import FindCardsStuckInPending
from .find_errors.vop_cards_needing_activations import FindVopCardsNeedingActivation
from .find_errors.deleted_vop_cards_with_activations import FindDeletedVopCardsWithActivations


# New scripts which find records to correct should be imported above and mapped in script functions
# Define name and title here.  Only Scripts names in SCRIPT_CLASSES will be have a link on /admin/scripts/ page

class DataScripts(IntEnum):
    METIS_CALLBACK = auto()       # This is a placeholder in scripts results for call back data and not a real script
    DEL_VOP_WITH_ACT = auto()
    ACTIVATE_ACTIVATING = auto()
    REPEAT_VOP_ENROL_STUCK_CARDS = auto()


SCRIPT_TITLES = {
    DataScripts.METIS_CALLBACK: "Metis Callback (results container)",
    DataScripts.DEL_VOP_WITH_ACT: "Deleted VOP cards with remaining activations",
    DataScripts.ACTIVATE_ACTIVATING: "Stuck in Activating with active link",
    DataScripts.REPEAT_VOP_ENROL_STUCK_CARDS: "Cards stuck in pending may need removing and re-adding",
}

SCRIPT_CLASSES = {
    DataScripts.DEL_VOP_WITH_ACT: FindDeletedVopCardsWithActivations,
    DataScripts.ACTIVATE_ACTIVATING: FindVopCardsNeedingActivation,
    DataScripts.REPEAT_VOP_ENROL_STUCK_CARDS: FindCardsStuckInPending,
}
# End of new script definition - you do not need to do anything else to add a new find script
# But you may need to add one or more corrective actions see models and admin actions
