import logging

import arrow
from rest_framework.generics import get_object_or_404

from hermes.channels import Permit
from history.enums import SchemeAccountJourney
from history.utils import user_info
from payment_card import metis
from payment_card.models import PaymentCardAccount
from scheme.mixins import SchemeAccountJoinMixin
from scheme.models import Scheme, SchemeAccount
from ubiquity.models import PaymentCardAccountEntry, SchemeAccountEntry, ServiceConsent
from ubiquity.tasks import (
    async_join,
    async_link,
    auto_link_membership_to_payments,
    deleted_membership_card_cleanup,
    deleted_payment_card_cleanup,
    deleted_service_cleanup,
)
from ubiquity.views import AutoLinkOnCreationMixin, MembershipCardView
from user.models import CustomUser

logger = logging.getLogger("messaging")


def credentials_to_key_pairs(cred_list: list) -> dict:
    ret = {}
    for item in cred_list:
        ret[item["credential_slug"]] = item["value"]
    return ret


def set_auth_provided(scheme_account: SchemeAccount, user: CustomUser, new_value: bool) -> None:
    link = SchemeAccountEntry.objects.get(scheme_account_id=scheme_account.id, user_id=user.id)
    link.auth_provided = new_value
    link.save(update_fields=["auth_provided"])


def post_payment_account(message: dict) -> None:
    # Calls Metis to enrol payment card if account was just created.
    logger.info("Handling onward POST/payment_account journey from Angelia. ")

    bundle_id = message.get("channel_id")
    payment_card_account = PaymentCardAccount.objects.get(pk=message.get("payment_account_id"))
    user = CustomUser.objects.get(pk=message.get("user_id"))

    if message.get("auto_link"):
        AutoLinkOnCreationMixin.auto_link_to_membership_cards(user, payment_card_account, bundle_id, just_created=True)

    if message.get("created"):
        metis.enrol_new_payment_card(payment_card_account, run_async=False)


def delete_payment_account(message: dict) -> None:
    logger.info("Handling DELETE/payment_account journey from Angelia.")
    query = {"user_id": message["user_id"], "payment_card_account_id": message["payment_account_id"]}

    get_object_or_404(PaymentCardAccountEntry.objects, **query).delete()

    deleted_payment_card_cleanup(
        payment_card_id=message["payment_account_id"],
        payment_card_hash=None,
        history_kwargs={"user_info": user_info(user_id=message["user_id"], channel=message["channel_id"])},
    )


def loyalty_card_register(message: dict) -> None:
    logger.info("Handling loyalty_card REGISTER journey")

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
            auto_link_membership_to_payments(
                payment_cards_to_link=payment_cards_to_link,
                membership_card=account,
                history_kwargs={"user_info": user_info(user_id=user.id, channel=message.get("channel"))},
            )

    MembershipCardView._handle_registration_route(
        user=user,
        permit=permit,
        scheme_acc_entry=sch_acc_entry,
        scheme_questions=questions,
        registration_fields=all_credentials_and_consents,
        scheme=scheme,
        account=account,
    )


def loyalty_card_authorise(message: dict) -> None:

    logger.info("Handling loyalty_card authorisation")
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

    if message.get("primary_auth"):
        # primary_auth is used to indicate that this user has demonstrated the authority to authorise and set the status
        # of this card (i.e. they are not secondary to an authorised user of this card.)
        account.set_pending()
        async_link(
            auth_fields=all_credentials_and_consents,
            scheme_account_id=account.id,
            user_id=user.id,
            payment_cards_to_link=payment_cards_to_link,
        )

    elif payment_cards_to_link:
        # if the request does not come from a primary_auth, then we will just auto-link this user's cards without
        # affecting the state of the loyalty card.
        auto_link_membership_to_payments(
            payment_cards_to_link=payment_cards_to_link,
            membership_card=account,
            history_kwargs={
                "user_info": user_info(user_id=user.id, channel=message.get("channel")),
            },
        )


def loyalty_card_join(message: dict) -> None:

    logger.info("Handling loyalty_card join")
    if message.get("auto_link"):
        payment_cards_to_link = PaymentCardAccountEntry.objects.filter(user_id=message.get("user_id")).values_list(
            "payment_card_account_id", flat=True
        )
    else:
        payment_cards_to_link = []

    all_credentials_and_consents = credentials_to_key_pairs(message.get("join_fields"))

    if message.get("consents"):
        all_credentials_and_consents.update({"consents": message["consents"]})

    user = CustomUser.objects.get(pk=message.get("user_id"))
    account = SchemeAccount.objects.get(pk=message.get("loyalty_card_id"))
    scheme = Scheme.objects.get(pk=message.get("loyalty_plan_id"))
    permit = Permit(bundle_id=message["channel"], user=user)
    channel = message.get("channel")

    validated_data, serializer, _ = SchemeAccountJoinMixin.validate(
        data=all_credentials_and_consents,
        scheme_account=account,
        user=user,
        permit=permit,
        join_scheme=scheme,
    )

    async_join(
        scheme_account_id=account.id,
        user_id=user.id,
        serializer=serializer,
        scheme_id=scheme.id,
        validated_data=validated_data,
        channel=channel,
        payment_cards_to_link=payment_cards_to_link,
        history_kwargs={
            "user_info": user_info(user_id=user.id, channel=channel),
            "journey": SchemeAccountJourney.ENROL.value,
        },
    )


def delete_loyalty_card(message: dict) -> None:

    user = CustomUser.objects.get(pk=message.get("user_id"))
    account = SchemeAccount.objects.get(pk=message.get("loyalty_card_id"))

    SchemeAccountEntry.objects.filter(scheme_account=account, user=user).delete()
    deleted_membership_card_cleanup(
        account.id,
        arrow.utcnow().format(),
        user.id,
        history_kwargs={"user_info": user_info(user_id=user.id, channel=message.get("channel"))},
    )


def delete_user(message: dict) -> None:
    consent_data = None
    user_id = message.get("user_id")
    channel = message.get("channel")

    try:
        user = CustomUser.objects.get(pk=user_id)
    except CustomUser.DoesNotExist:
        logger.exception(f"Could not delete user {user_id} - account not found.")
    else:
        try:
            consent = ServiceConsent.objects.get(pk=user_id)
            consent_data = {"email": user.email, "timestamp": consent.timestamp}
        except ServiceConsent.DoesNotExist:
            logger.exception(f"Service Consent data could not be found whilst deleting user {user_id} .")

        user.soft_delete()
        deleted_service_cleanup(
            user_id=user_id,
            consent=consent_data,
            history_kwargs={"user_info": user_info(user_id=user_id, channel=channel)},
        )
        logger.info(f"User {user_id} successfully deleted. ")

def refresh_balance(eh: dict) -> None:
    print("Hello There API Messaging - Refresh Balance Called...")

