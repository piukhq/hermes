import uuid
from typing import TYPE_CHECKING

from olympus_messaging import JoinApplication, LoyaltyCardRemoved, Message

from api_messaging.message_broker import ProducerQueues, sending_service
from history.data_warehouse import get_main_answer

if TYPE_CHECKING:
    from ubiquity.models import SchemeAccount


def to_midas(message: Message, x_azure_ref: str | None = None) -> None:
    headers = message.metadata
    headers["X-azure-ref"] = x_azure_ref
    sending_service.queues[ProducerQueues.MIDAS.name].send_message(message.body, headers=headers)


def send_midas_join_request(
    channel: str,
    bink_user_id: int,
    request_id: int,
    loyalty_plan: str,
    account_id: str,
    encrypted_credentials: str,
    headers: dict | None = None,
) -> None:
    message = JoinApplication(
        channel=channel,
        transaction_id=str(uuid.uuid1()),
        bink_user_id=str(bink_user_id),
        request_id=str(request_id),
        loyalty_plan=loyalty_plan,
        account_id=account_id,
        join_data={"encrypted_credentials": encrypted_credentials},
    )

    to_midas(message, headers.get("X-azure-ref", None) if headers else None)


def send_midas_last_pll_per_channel_group_event(
    channel_slug: str,
    user_id: int | str,
    scheme_account: "SchemeAccount",
    headers: dict | None = None,
) -> None:
    """
    This event is sent to identify when PLL has been deactivated for a loyalty card in
    either a trusted channel or all other channels (as a single group, not individually).
    """

    message = LoyaltyCardRemoved(
        # message header data
        channel=channel_slug,
        transaction_id=str(uuid.uuid1()),
        bink_user_id=str(user_id),
        request_id=str(scheme_account.id),
        account_id=get_main_answer(scheme_account),
        loyalty_plan=scheme_account.scheme.slug,
    )
    to_midas(message, headers.get("X-azure-ref", None) if headers else None)
