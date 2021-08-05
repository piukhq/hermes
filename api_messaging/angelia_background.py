from history.utils import user_info
from payment_card import metis
from payment_card.models import PaymentCardAccount
from rest_framework.generics import get_object_or_404
from ubiquity.views import AutoLinkOnCreationMixin
from ubiquity.models import PaymentCardAccountEntry
from scheme.models import SchemeAccount
from ubiquity.tasks import deleted_payment_card_cleanup, async_add_field_only_link, auto_link_membership_to_payments
from user.models import CustomUser

import logging

logger = logging.getLogger("Messaging")


def post_payment_account(message: dict):
    # Calls Metis to enrol payment card if account was just created.
    logger.info('Handling onward POST/payment_account journey from Angelia.')

    bundle_id = message.get("channel_id")
    payment_card_account = PaymentCardAccount.objects.get(pk=message.get("payment_account_id"))
    user = CustomUser.objects.get(pk=message.get("user_id"))

    if message.get("auto_link"):
        AutoLinkOnCreationMixin.auto_link_to_membership_cards(
            user, payment_card_account, bundle_id, just_created=True
        )

    if message.get("created"):
        metis.enrol_new_payment_card(payment_card_account, run_async=False)


def delete_payment_account(message: dict):
    logger.info('Handling DELETE/payment_account journey from Angelia.')
    query = {"user_id": message['user_id'],
             "payment_card_account_id": message['payment_account_id']}

    get_object_or_404(PaymentCardAccountEntry.objects, **query).delete()

    deleted_payment_card_cleanup(payment_card_id=message['payment_account_id'],
                                 payment_card_hash=None,
                                 history_kwargs={"user_info": user_info(user_id=message['user_id'],
                                                                        channel=message['channel_id'])})


def loyalty_card_add(message: dict):
    logger.info('Handling loyalty_card ADD journey')
    if message['auto_link']:
        payment_cards_to_link = PaymentCardAccountEntry.objects.filter(user_id=message['user_id']).values_list(
            "payment_card_account_id", flat=True
        )
    else:
        payment_cards_to_link = []

    if message['created']:
        async_add_field_only_link(message['loyalty_card_id'], payment_cards_to_link)
    else:
        auto_link_membership_to_payments(payment_cards_to_link,
                                         scheme=SchemeAccount.objects.get(id=message['loyalty_card_id']))
