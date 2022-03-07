import logging

from django.conf import settings

from api_messaging.message_broker import SendingService

logger = logging.getLogger("messaging")

message_sender = SendingService(
    dsn=settings.RABBIT_DSN,
    log_to=logger,
)


def to_data_warehouse(event_type: str, user_id: int, channel_slug: str, event_date: str, model_data: dict) -> None:
    headers = {}
    payload = None
    if event_type == "event.user.created.api":
        payload = {
            "event_type": event_type,
            "origin": "channel",
            "channel": channel_slug,
            "event_date_time": event_date,
            "external_user_ref": model_data.get("external_id"),
            "internal_user_ref": user_id,
            "email": model_data.get("email"),
        }

    if payload:
        message_sender.send(payload, headers, settings.WAREHOUSE_QUEUE_NAME)
