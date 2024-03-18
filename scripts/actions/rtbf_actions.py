from csv import DictReader
from pathlib import Path
from typing import TYPE_CHECKING

from celery import chord, group

from scripts.enums import FileScriptStatuses
from scripts.tasks.rtbf_tasks import (
    right_to_be_forgotten_batch_fail_handler_task,
    right_to_be_forgotten_batch_success_handler_task,
    right_to_be_forgotten_batch_task,
)

if TYPE_CHECKING:
    from scripts.models import FileScript


def do_right_to_be_forgotten(entry: "FileScript") -> bool:
    input_file = Path(entry.input_file.path)
    ids = []
    tasks = []
    with input_file.open("r") as stream:
        reader = DictReader(stream)

        for count, row in enumerate(reader, start=1):
            ids.append(row["ids"])

            if count % entry.batch_size == 0:
                tasks.append(right_to_be_forgotten_batch_task.s(ids=ids, entry_id=entry.id))
                ids = []

    if ids:
        tasks.append(right_to_be_forgotten_batch_task.s(ids=ids, entry_id=entry.id))

    tasks_n = len(tasks)
    result = chord(group(tasks))(
        right_to_be_forgotten_batch_success_handler_task.s(entry_id=entry.id).on_error(
            right_to_be_forgotten_batch_fail_handler_task.s(entry_id=entry.id)
        )
    )
    result.parent.save()

    entry.celery_group_id = result.parent.id
    entry.created_tasks_n = tasks_n
    entry.status = FileScriptStatuses.IN_PROGRESS
    entry.save(update_fields=["status", "celery_group_id", "created_tasks_n"])
    return True
