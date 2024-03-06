from csv import DictWriter
from datetime import datetime
from time import sleep
from typing import TYPE_CHECKING

from celery import shared_task
from celery.result import GroupResult
from django.core.files.base import ContentFile
from typing_extensions import TypedDict

from scripts.enums import ShirleyStatuses

if TYPE_CHECKING:
    from scripts.models import ShirleyYouCantBeSerious

    class SuccessfulType(TypedDict):
        ids: int

    class FailedType(TypedDict):
        ids: int
        reason: str

    class ResultType(TypedDict):
        successful: list[SuccessfulType]
        failed: list[FailedType]

    GroupResultType = list[ResultType]


def write_files_and_status(group_result: "GroupResultType", entry: "ShirleyYouCantBeSerious"):
    failed_file = ContentFile("", name=f"{datetime.now().isoformat()}_failed.csv")
    success_file = ContentFile("", name=f"{datetime.now().isoformat()}_success.csv")
    all_successful = True

    with failed_file.open("w") as fail_output, success_file.open("w") as success_output:
        fail_writer = DictWriter(fail_output, fieldnames=["ids", "reason"])
        success_writer = DictWriter(success_output, fieldnames=["ids"])
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

    entry.status = ShirleyStatuses.DONE
    entry.status_description = description
    entry.failed_file = failed_file
    entry.success_file = success_file
    entry.celery_group_id = None
    entry.save(update_fields=["status", "failed_file", "success_file", "status_description", "celery_group_id"])


@shared_task
def right_to_be_forgotten_success_handler_task(
    group_result: "GroupResultType", *, entry: "ShirleyYouCantBeSerious"
) -> None:
    entry.refresh_from_db(fields=["celery_group_id"])
    celery_group = GroupResult.restore(entry.celery_group_id)
    write_files_and_status(group_result, entry)
    celery_group.forget()


@shared_task
def right_to_be_forgotten_fail_handler_task(*_args, entry: "ShirleyYouCantBeSerious") -> None:
    entry.refresh_from_db(fields=["celery_group_id"])
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


@shared_task
def right_to_be_forgotten_task(ids: list[str]) -> "ResultType":
    result: "ResultType" = {"failed": [], "successful": []}

    for uid in ids:
        success, reason = actual_rtbf_logic_goes_here(uid)
        if success:
            result["successful"].append({"ids": uid})
        else:
            result["failed"].append({"ids": uid, "reason": reason})

    return result


def actual_rtbf_logic_goes_here(user_id: str) -> tuple[bool, str]:
    sleep(0.1)

    # simulate unhandled error in rtfb logic
    if user_id == "FAIL":
        raise ValueError("Test Error")

    # simulate handled error in rtfb logic
    if "F" in user_id:
        return False, "Test Failure"

    return True, ""
