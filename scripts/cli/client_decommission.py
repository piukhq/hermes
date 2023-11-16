from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, cast

from django.conf import settings
from loguru import logger
from tqdm import tqdm

from hermes.settings import azure_ref_patcher
from scripts.cli.utils.log_to_file import loguru_set_file_sink
from ubiquity.models import ServiceConsent
from ubiquity.tasks import deleted_service_cleanup
from user.models import CustomUser

if TYPE_CHECKING:
    from django.core.management.base import OutputWrapper


def handle_user_deletion(user: "CustomUser") -> bool:
    consent_data: "dict[str, str | datetime] | None" = None
    success = True
    try:
        try:
            consent = cast(ServiceConsent, user.serviceconsent)
            consent_data = {"email": user.email, "timestamp": consent.timestamp}
        except CustomUser.serviceconsent.RelatedObjectDoesNotExist:
            logger.error("Service Consent data could not be found whilst deleting user %d .", user.id)

        if user.is_active:
            user.soft_delete()
            msg = "User %d successfully deleted."
        else:
            msg = "User %d already deleted, but delete cleanup has run successfully"

        deleted_service_cleanup(user_id=user.id, consent=consent_data, user=user)
        logger.info(msg, user.id)
    except CustomUser.DoesNotExist:
        pass
    except Exception as e:
        logger.exception("Unexpected error.", exc_info=e)
        success = False

    return success


def decommission_client(
    *,
    client_name: str,
    exclude_test_users: bool,
    batch_size: int,
    log_path: str,
    is_dry_run: bool,
    stdout: "OutputWrapper",
) -> str:
    failed_deletion = []
    filters = {"client__name__iexact": client_name}
    if exclude_test_users:
        filters |= {
            "is_staff": False,
            "is_tester": False,
        }

    users = CustomUser.objects.select_related("serviceconsent").filter(**filters)
    if is_dry_run:
        n_affected_users = users.count()
        stdout.write(f"{n_affected_users} users would be affected for client {client_name}")
    else:
        stdout.write(f"Normal logging will be redirected to file {log_path}")
        loguru_set_file_sink(
            path=Path(log_path),
            json_logging=settings.JSON_LOGGING,
            sink_log_level=settings.MASTER_LOG_LEVEL,
            show_pid=True,
            custom_patcher=azure_ref_patcher,
        )

        with tqdm(total=users.count()) as pbar:
            for user in users.iterator(batch_size):
                pbar.set_description(f"Deleting User {user.id}")
                if not handle_user_deletion(user):
                    failed_deletion.append(user.id)

                pbar.update(1)

    match failed_deletion, is_dry_run:
        case _, True:
            msg = "Dry run completed no user was affected."
        case [], False:
            msg = "All users deleted successfully"
        case _:
            msg = f"Cleanup failed for users:\n{failed_deletion}\nlog details can be found in {log_path}"

    return msg
