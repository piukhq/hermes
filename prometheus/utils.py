from history.utils import get_channel_from_context
from prometheus.metrics import membership_card_status_change_counter
from ubiquity.reason_codes import ubiquity_status_translation


def capture_membership_card_status_change_metric(scheme_slug: str, old_status: int, new_status: int) -> None:
    old_status = ubiquity_status_translation.get(old_status, "unknown")
    new_status = ubiquity_status_translation.get(new_status, "unknown")
    if old_status != new_status:
        membership_card_status_change_counter.labels(
            channel=get_channel_from_context(),
            scheme=scheme_slug,
            status_change=f"{old_status} -> {new_status}"
        ).inc()
