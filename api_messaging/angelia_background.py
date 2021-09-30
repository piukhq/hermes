from history.utils import user_info
from payment_card import metis
from payment_card.models import PaymentCardAccount
from rest_framework.generics import get_object_or_404
from ubiquity.views import AutoLinkOnCreationMixin
from ubiquity.models import PaymentCardAccountEntry, SchemeAccountEntry
from scheme.models import SchemeAccount
from ubiquity.tasks import deleted_payment_card_cleanup, auto_link_membership_to_payments, async_link, \
    deleted_membership_card_cleanup
from user.models import CustomUser
from hermes.channels import Permit
from ubiquity.views import MembershipCardView

import logging
import arrow

logger = logging.getLogger("messaging")


def credentials_to_key_pairs(cred_list: list) -> dict:
    ret = {}
    for item in cred_list:
        ret[item['credential_slug']] = item['value']
    return ret


def set_auth_provided(scheme_account: SchemeAccount, user: CustomUser, new_value: bool) -> None:
    link = SchemeAccountEntry.objects.get(scheme_account_id=scheme_account.id, user_id=user.id)
    link.auth_provided = new_value
    link.save(update_fields=['auth_provided'])


def post_payment_account(message: dict) -> None:
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


def delete_payment_account(message: dict) -> None:
    logger.info('Handling DELETE/payment_account journey from Angelia.')
    query = {"user_id": message['user_id'],
             "payment_card_account_id": message['payment_account_id']}

    get_object_or_404(PaymentCardAccountEntry.objects, **query).delete()

    deleted_payment_card_cleanup(payment_card_id=message['payment_account_id'],
                                 payment_card_hash=None,
                                 history_kwargs={"user_info": user_info(user_id=message['user_id'],
                                                                        channel=message['channel_id'])})


def loyalty_card_register(message: dict) -> None:
    logger.info('Handling loyalty_card REGISTER journey')

    all_credentials_and_consents = {}
    all_credentials_and_consents.update(credentials_to_key_pairs(message.get("register_fields")))

    if message.get("consents"):
        all_credentials_and_consents.update({"consents": message["consents"]})

    user = CustomUser.objects.get(pk=message.get("user_id"))
    permit = Permit(bundle_id=message["channel"], user=user)
    account = SchemeAccount.objects.get(pk=message.get("loyalty_card_id"))
    sch_acc_entry = account.schemeaccountentry_set.get(user=user)
    scheme = account.scheme
    questions = scheme.questions.all()

    if message.get("auto_link"):
        payment_cards_to_link = PaymentCardAccountEntry.objects.filter(user_id=user.id).values_list(
            "payment_card_account_id", flat=True
        )
        if payment_cards_to_link:
            auto_link_membership_to_payments(payment_cards_to_link=payment_cards_to_link,
                                             membership_card=account,
                                             history_kwargs={
                                                 "user_info": user_info(
                                                     user_id=user.id, channel=message.get("channel")
                                                 )})

    MembershipCardView._handle_registration_route(
        user=user,
        permit=permit,
        scheme_acc_entry=sch_acc_entry,
        scheme_questions=questions,
        registration_fields=all_credentials_and_consents,
        scheme=scheme,
        account=account
    )


def loyalty_card_authorise(message: dict) -> None:

    logger.info('Handling loyalty_card authorisation')
    if message.get("auto_link"):
        payment_cards_to_link = PaymentCardAccountEntry.objects.filter(user_id=message.get("user_id")).values_list(
            "payment_card_account_id", flat=True
        )
    else:
        payment_cards_to_link = []

    all_credentials_and_consents = {}
    all_credentials_and_consents.update(credentials_to_key_pairs(message.get("authorise_fields")))

    if message.get("consents"):
        all_credentials_and_consents.update({"consents": message["consents"]})

    user = CustomUser.objects.get(pk=message.get("user_id"))
    account = SchemeAccount.objects.get(pk=message.get("loyalty_card_id"))

    set_auth_provided(account, user, True)

    if message.get("created"):
        # For an Add_and_auth journey, 'created' indicates a newly created account
        # For an Authorise journey, 'created' equates to primary_auth (i.e. that this user is free to set and 'control'
        # primary auth credentials)
        account.set_pending()
        async_link(auth_fields=all_credentials_and_consents,
                   scheme_account_id=account.id,
                   user_id=user.id,
                   payment_cards_to_link=payment_cards_to_link,
                   )

    elif payment_cards_to_link:
        auto_link_membership_to_payments(payment_cards_to_link=payment_cards_to_link,
                                         membership_card=account,
                                         history_kwargs={
                                             "user_info": user_info(
                                                 user_id=user.id, channel=message.get("channel")
                                             ),
                                         })


def delete_loyalty_card(message: dict) -> None:

    user = CustomUser.objects.get(pk=message.get("user_id"))
    account = SchemeAccount.objects.get(pk=message.get("loyalty_card_id"))

    SchemeAccountEntry.objects.filter(scheme_account=account, user=user).delete()
    deleted_membership_card_cleanup(
        account.id,
        arrow.utcnow().format(),
        user.id,
        history_kwargs={
            "user_info": user_info(
                user_id=user.id, channel=message.get("channel")
            )
        },
    )
