from collections import defaultdict
from csv import DictReader
from io import TextIOWrapper
from typing import TYPE_CHECKING

from celery import chord, group

from scripts.enums import FileScriptStatuses

if TYPE_CHECKING:
    from celery import Task

    from scripts.models import FileScript


class FileScriptAction:
    required_task_keys = ["ids"]
    forwarded_context_keys = ["script_runner"]

    def __init__(
        self,
        process_batch_task: "Task",
        success_handler_task: "Task",
        fail_handler_task: "Task",
        required_task_keys: list[str] | None = None,
    ) -> None:
        self.process_batch_task = process_batch_task
        self.success_handler_task = success_handler_task
        self.fail_handler_task = fail_handler_task
        self.required_task_keys = required_task_keys or self.required_task_keys

    def __call__(self, entry: "FileScript", context: dict):
        tasks_params: dict[str, list[int]] = defaultdict(list)
        tasks: list["Task"] = []
        forwarded_context = {key: context.get(key) for key in self.forwarded_context_keys}

        # Opening the file in binary mode and then wrapping it in TextIOWrapper to handle the encoding, instead
        # of just opening the file as string, due to azure blob storage not supporting text mode.
        with entry.input_file.open("rb") as stream:
            reader = DictReader(TextIOWrapper(stream, encoding="utf-8"))

            for count, row in enumerate(reader, start=1):
                for key in self.required_task_keys:
                    # csv columns should have been validated before reaching this point via
                    # INPUT_FILE_VALIDATION_BY_CORRECTION in scripts/corrections/file_scripts.py
                    tasks_params[key].append(row[key])

                if count % entry.batch_size == 0:
                    tasks.append(self.process_batch_task.s(**tasks_params, entry_id=entry.id, **forwarded_context))
                    for key in tasks_params:
                        tasks_params[key] = []

        if any(bool(val) for val in tasks_params.values()):
            tasks.append(self.process_batch_task.s(**tasks_params, entry_id=entry.id, **forwarded_context))

        tasks_n = len(tasks)
        result = chord(group(tasks))(
            self.success_handler_task.s(entry_id=entry.id).on_error(self.fail_handler_task.s(entry_id=entry.id))
        )
        result.parent.save()

        entry.celery_group_id = result.parent.id
        entry.created_tasks_n = tasks_n
        entry.status = FileScriptStatuses.IN_PROGRESS
        entry.save(update_fields=["status", "celery_group_id", "created_tasks_n"])
        return True
