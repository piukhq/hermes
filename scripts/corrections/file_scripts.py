from collections.abc import Callable
from dataclasses import dataclass

from scripts.actions.file_scripts import FileScriptAction
from scripts.corrections import Correction
from scripts.tasks.file_script_tasks import file_script_fail_handler_task, file_script_success_handler_task
from scripts.tasks.file_script_tasks.account_closure_tasks import account_closure_batch_task
from scripts.tasks.file_script_tasks.rtbf_tasks import right_to_be_forgotten_batch_task


@dataclass
class ColumnTypeSchema:
    name: str
    is_valid: Callable[[str], bool]


INT_COLUMN_TYPE_VALIDATION = ColumnTypeSchema(
    name="integer",
    is_valid=lambda value: value.isdecimal(),
)

INPUT_FILE_VALIDATION_BY_CORRECTION = {
    Correction.RTBF: {"ids": INT_COLUMN_TYPE_VALIDATION},
    Correction.ACCOUNT_CLOSURE: {"ids": INT_COLUMN_TYPE_VALIDATION},
}

MAPPED_ACTIONS = {
    Correction.RTBF: FileScriptAction(
        process_batch_task=right_to_be_forgotten_batch_task,
        success_handler_task=file_script_success_handler_task,
        fail_handler_task=file_script_fail_handler_task,
    ),
    Correction.ACCOUNT_CLOSURE: FileScriptAction(
        process_batch_task=account_closure_batch_task,
        success_handler_task=file_script_success_handler_task,
        fail_handler_task=file_script_fail_handler_task,
    ),
}


def apply_file_script_mapped_action(entry: object, script_runner_id: str):
    if entry.correction not in MAPPED_ACTIONS:
        return False

    return MAPPED_ACTIONS[entry.correction](entry, context={"script_runner_id": script_runner_id})
