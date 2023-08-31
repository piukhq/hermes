import uuid

from olympus_messaging import JoinApplication, LoyaltyCardRemovedBink, Message

from api_messaging.message_broker import ProducerQueues, sending_service
from history.data_warehouse import get_main_answer
from ubiquity.models import SchemeAccountEntry


def to_midas(message: Message, x_azure_ref: str | None = None) -> None:
    message.metadata["X-azure-ref"] = x_azure_ref
    sending_service.queues[ProducerQueues.MIDAS.name].send_message(message.body, headers=message.metadata)


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


def send_midas_last_loyalty_card_removed(scheme_account_entry: SchemeAccountEntry, headers: dict | None = None):
    message = LoyaltyCardRemovedBink(
        # message header data
        channel=scheme_account_entry.user.bundle_id,
        transaction_id=str(uuid.uuid1()),
        bink_user_id=str(scheme_account_entry.user.id),
        request_id=str(scheme_account_entry.scheme_account.id),
        account_id=get_main_answer(scheme_account_entry.scheme_account),
        loyalty_plan=scheme_account_entry.scheme_account.scheme.slug,
        # message body data
        message_data={"status": str(scheme_account_entry.link_status)},
    )
    to_midas(message, headers.get("X-azure-ref", None) if headers else None)
