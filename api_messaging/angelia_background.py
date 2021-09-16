from history.utils import user_info
from payment_card import metis
from payment_card.models import PaymentCardAccount
from rest_framework.generics import get_object_or_404
from ubiquity.views import AutoLinkOnCreationMixin
from ubiquity.models import PaymentCardAccountEntry
from scheme.models import SchemeAccount
from ubiquity.tasks import deleted_payment_card_cleanup, auto_link_membership_to_payments, async_link
from user.models import CustomUser

import logging

logger = logging.getLogger("Messaging")


def credentials_to_key_pairs(cred_list: list) -> dict:
    ret = {}
    for item in cred_list:
        ret[item['credential_slug']] = item['value']
    return ret


def post_payment_account(message: dict):
    # Calls Metis to enrol payment card if account was just created.
    logger.info('Handling onward POST/payment_account journey from Angelia. ')

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


def loyalty_card_register(message: dict):
    logger.info('Handling loyalty_card REGISTER journey')

    all_credentials_and_consents = {}

    for cred in message["register_fields"]:
        all_credentials_and_consents.update({cred["credential_slug"]: cred["value"]})

    all_credentials_and_consents.update({"consents": message["consents"]})

    pass

    # Todo: refactor credentials and consents
    # Todo: create Permit
    # Todo: Hook into SchemeAccountJoinMixin.handle_join_request


def loyalty_card_add_and_auth(message: dict):
    logger.info('Handling loyalty_card ADD and Authorise journey')
    if message.get("auto_link"):
        payment_cards_to_link = PaymentCardAccountEntry.objects.filter(user_id=message.get("user_id")).values_list(
            "payment_card_account_id", flat=True
        )
    else:
        payment_cards_to_link = []

    if message.get("created"):
        auth_fields = credentials_to_key_pairs(message.get("auth_fields"))
        async_link(
            auth_fields, message.get("loyalty_card_id"), message.get("user_id"), payment_cards_to_link
        )
    elif payment_cards_to_link:
        scheme_account = SchemeAccount.objects.get(id=message.get("loyalty_card_id"))
        auto_link_membership_to_payments(
            payment_cards_to_link,
            scheme_account,
            history_kwargs={
                "user_info": user_info(user_id=message.get("user_id"), channel=message.get("channel"))
            }
        )
