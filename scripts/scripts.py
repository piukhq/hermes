from enum import IntEnum, auto

from .vop_scripts import find_deleted_vop_cards_with_activations


# New scripts which find records to correct should be imported above and mapped in script functions
# Define name and title here.  Only Scripts names in SCRIPT_FUNCTIONS will be have a link on /admin/scripts/ page
class DataScripts(IntEnum):
    METIS_CALLBACK = auto()       # This is a placeholder in scripts results for call back data and not a real script
    DEL_VOP_WITH_ACT = auto()
    ACTIVATE_ACTIVATING = auto()
    REPEAT_VOP_ENROL_STUCK_CARDS = auto()


SCRIPT_TITLES = {
    DataScripts.METIS_CALLBACK: "Metis Callback (results container)",
    DataScripts.DEL_VOP_WITH_ACT: "Deleted VOP cards with remaining activations",
    DataScripts.ACTIVATE_ACTIVATING: "Stuck in Activating with active link",
    DataScripts.REPEAT_VOP_ENROL_STUCK_CARDS: "Cards stuck in pending may have enrolled so Un-Enrol and RE-Enrol",
}

SCRIPT_FUNCTIONS = {
    DataScripts.DEL_VOP_WITH_ACT: find_deleted_vop_cards_with_activations,
    DataScripts.ACTIVATE_ACTIVATING: find_deleted_vop_cards_with_activations,
    DataScripts.REPEAT_VOP_ENROL_STUCK_CARDS: find_deleted_vop_cards_with_activations,
}
# End of new script definition - you do not need to do anything else to add a new find script
# But you may need to add one or more corrective actions see models and admin actions
