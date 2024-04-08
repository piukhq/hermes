from codecs import getwriter
from collections.abc import Callable
from csv import DictWriter
from typing import TYPE_CHECKING

from celery import shared_task
from celery.result import GroupResult
from django.core.files.base import ContentFile
from typing_extensions import TypedDict

from scripts.enums import FileScriptStatuses
from scripts.models import FileScript

if TYPE_CHECKING:

    class SuccessfulType(TypedDict):
        ids: int

    class FailedType(TypedDict):
        ids: int
        reason: str

    class ResultType(TypedDict):
        successful: list[SuccessfulType]
        failed: list[FailedType]

    # this is a dict instead of a dataclass to help with serialization
    GroupResultType = list[ResultType]

BytesStreamWriter = getwriter("utf-8")


def write_files_and_status(group_result: list[dict], entry: "FileScript"):
    # have to setup the file as bytes and use a codec to write utf-8 as azure storage only supports bytes file
    failed_file = ContentFile(b"", name=f"FS{entry.id}_failed.csv")
    success_file = ContentFile(b"", name=f"FS{entry.id}_success.csv")

    all_successful = True

    with failed_file.open("wb") as fail_output, success_file.open("wb") as success_output:
        fail_writer = DictWriter(BytesStreamWriter(fail_output), fieldnames=["ids", "reason"])
        success_writer = DictWriter(BytesStreamWriter(success_output), fieldnames=["ids"])
        fail_writer.writeheader()
        success_writer.writeheader()
        for result in group_result:
            if failed := result["failed"]:
                fail_writer.writerows(failed)
                all_successful = False
            if successful := result["successful"]:
                success_writer.writerows(successful)

    description = "Task completed"
    if all_successful:
        description += ", no further action needed."
    else:
        description += ", but with some failures. Check the failed file."

    entry.status = FileScriptStatuses.DONE
    entry.status_description = description
    entry.failed_file = failed_file
    entry.success_file = success_file
    entry.celery_group_id = None
    entry.save(update_fields=["status", "failed_file", "success_file", "status_description", "celery_group_id"])


@shared_task
def file_script_success_handler_task(group_result: "GroupResultType", *, entry_id: int) -> None:
    entry = FileScript.objects.get(id=entry_id)
    celery_group = GroupResult.restore(entry.celery_group_id)
    write_files_and_status(group_result, entry)
    celery_group.forget()


@shared_task
def file_script_fail_handler_task(*_args, entry_id: int) -> None:
    entry = FileScript.objects.get(id=entry_id)
    celery_group = GroupResult.restore(entry.celery_group_id)
    group_result: GroupResultType = []
    for result in celery_group.results:
        if result.successful():
            group_result.append(result.get(disable_sync_subtasks=False))
        else:
            group_result.append(
                {
                    "failed": [{"ids": uid, "reason": repr(result.info)} for uid in result.kwargs["ids"]],
                    "successful": [],
                }
            )
            result.forget()

    write_files_and_status(group_result, entry)
    celery_group.forget()


def file_script_batch_task_base(
    ids: list[str], entry_id: int, script_runner_id: str, *, logic_fn: Callable[[str, int, str], tuple[bool, str]]
) -> "ResultType":
    result: "ResultType" = {"failed": [], "successful": []}

    for uid in ids:
        success, reason = logic_fn(uid, entry_id, script_runner_id)
        if success:
            result["successful"].append({"ids": uid})
        else:
            result["failed"].append({"ids": uid, "reason": reason})

    return result
