import logging
import uuid

from django.conf import settings

from api_messaging.message_broker import SendingService

logger = logging.getLogger("messaging")

message_sender = SendingService(
    dsn=settings.RABBIT_DSN,
    log_to=logger,
)


def to_midas(payload: dict, headers: dict = None) -> None:
    headers = headers or {}
    message_sender.send(payload, headers, settings.MIDAS_QUEUE_NAME)


def send_midas_join_request(
    channel: str, bink_user_id: int, request_id: int, loyalty_plan: str, account_id: str, join_data: str
) -> None:

    to_midas(
        payload={
            "type": "loyalty_account.join.application",
            "channel": channel,
            "transaction_id": uuid.uuid1(),
            "bink_user_id": str(bink_user_id),
            "request_id": str(request_id),
            "loyalty_plan": loyalty_plan,
            "account_id": account_id,
            "join_data": join_data,
        }
    )
