from csv import DictReader
from pathlib import Path
from typing import TYPE_CHECKING

from celery import chord, group

from scripts.enums import ShirleyStatuses
from scripts.tasks.shirley_tasks import (
    right_to_be_forgotten_fail_handler_task,
    right_to_be_forgotten_success_handler_task,
    right_to_be_forgotten_task,
)

if TYPE_CHECKING:
    from scripts.models import ShirleyYouCantBeSerious


def test_correction(entry: "ShirleyYouCantBeSerious") -> bool:
    input_file = Path(entry.input_file.path)
    ids = []
    tasks = []
    with input_file.open("r") as stream:
        reader = DictReader(stream)

        for count, row in enumerate(reader, start=1):
            ids.append(row["ids"])

            if count % entry.batch_size == 0:
                tasks.append(right_to_be_forgotten_task.s(ids=ids))
                ids = []

    if ids:
        tasks.append(right_to_be_forgotten_task.s(ids=ids))

    tasks_n = len(tasks)
    result = chord(group(tasks))(
        right_to_be_forgotten_success_handler_task.s(entry=entry).on_error(
            right_to_be_forgotten_fail_handler_task.s(entry=entry)
        )
    )
    result.parent.save()

    entry.celery_group_id = result.parent.id
    entry.created_tasks_n = tasks_n
    entry.status = ShirleyStatuses.IN_PROGRESS
    entry.save(update_fields=["status", "celery_group_id", "created_tasks_n"])
    return True
