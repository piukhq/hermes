from typing import TYPE_CHECKING, cast

from celery import shared_task

from hermes.utils import ctx
from scripts.tasks.file_script_tasks import file_script_batch_task_base
from ubiquity.tasks import deleted_service_cleanup
from user.models import CustomUser

if TYPE_CHECKING:
    from datetime import datetime

    from scripts.tasks.file_script_tasks import ResultType


def _account_closure(str_user_id: str, entry_id: int, script_runner_id: str) -> tuple[bool, str]:
    # 'script_runner_id' will be needed for WAL-3387 as the 'django_user_id' value
    user_id = int(str_user_id)

    ctx.x_azure_ref = f"Django Admin FileScript {entry_id}"
    headers: dict[str, str] = {"X-azure-ref": ctx.x_azure_ref, "X-Priority": "4"}

    try:
        user = cast(
            CustomUser,
            CustomUser.all_objects.select_related("serviceconsent")
            .prefetch_related("client__clientapplicationbundle_set", "schemeaccountentry_set", "scheme_account_set")
            .get(pk=user_id),
        )
    except CustomUser.DoesNotExist:
        return False, f"Could not delete user {user_id} - account not found."

    if not (channel := cast(str | None, user.bundle_id)):
        try:
            channel = cast(str, user.client.clientapplicationbundle_set.first().bundle_id)
        except Exception:
            channel = "unknown"

    try:
        consent_data: dict[str, "str | datetime"] = {}
        if hasattr(user, "serviceconsent"):
            consent_data = {"email": user.email, "timestamp": user.serviceconsent.timestamp}

        if user.is_active:
            user.soft_delete()

        deleted_service_cleanup(user_id=user_id, user=user, consent=consent_data, channel_slug=channel, headers=headers)
    except Exception as e:
        return False, repr(e)

    return True, ""


@shared_task
def account_closure_batch_task(ids: list[str], entry_id: int, script_runner_id: str) -> "ResultType":
    return file_script_batch_task_base(ids, entry_id, script_runner_id, logic_fn=_account_closure)
