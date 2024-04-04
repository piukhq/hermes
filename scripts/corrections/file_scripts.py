from collections.abc import Callable
from dataclasses import dataclass

from scripts.actions.rtbf_actions import do_right_to_be_forgotten
from scripts.corrections import Correction


@dataclass
class ColumnTypeSchema:
    name: str
    is_valid: Callable[[str], bool]


INPUT_FILE_VALIDATION_BY_CORRECTION = {
    Correction.RTBF: {
        "ids": ColumnTypeSchema(
            name="integer",
            is_valid=lambda value: value.isdecimal(),
        ),
    },
}

MAPPED_ACTIONS = {
    Correction.RTBF: do_right_to_be_forgotten,
}


def apply_file_script_mapped_action(entry: object):
    if entry.correction not in MAPPED_ACTIONS:
        return False

    return MAPPED_ACTIONS[entry.correction](entry)
