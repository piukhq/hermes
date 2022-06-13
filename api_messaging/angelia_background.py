import logging
from datetime import datetime
from enum import Enum

import arrow
from rest_framework.generics import get_object_or_404

from hermes.channels import Permit
from history.data_warehouse import (
    add_and_auth_lc_event,
    add_auth_outcome,
    auth_outcome,
    auth_request_lc_event,
    join_request_lc_event,
    register_lc_event,
)
from history.enums import SchemeAccountJourney
from history.models import get_required_extra_fields
from history.serializers import get_body_serializer
from history.tasks import record_history
from history.utils import clean_history_kwargs, set_history_kwargs, user_info
from payment_card import metis
from payment_card.models import PaymentCardAccount
from scheme.mixins import SchemeAccountJoinMixin
from scheme.models import Scheme, SchemeAccount
from ubiquity.models import PaymentCardAccountEntry, SchemeAccountEntry, ServiceConsent
from ubiquity.tasks import (
    async_all_balance,
    async_join,
    async_link,
    auto_link_membership_to_payments,
    deleted_membership_card_cleanup,
    deleted_payment_card_cleanup,
    deleted_service_cleanup,
)
from ubiquity.views import AutoLinkOnCreationMixin, MembershipCardView
from user.models import CustomUser
from user.serializers import HistoryUserSerializer

logger = logging.getLogger("messaging")


class LoyaltyCardPath(Enum):
    AUTHORISE = 1
    ADD_AND_AUTHORISE = 2
    REGISTER = 3
    ADD_AND_REGISTER = 4


class AngeliaContext:
    """
    This context manager ensures that Angelia background tasks are wrapped in a similar context to Hermes requests
    and that the context is cleared down and not accidentally persisted between requests.

    The user_id and channel_slug are key permission objects that must be set in all messages.  They are also required
    for the history context to be set correctly

    Note: That hermes history context is saved in threading.local which per thread has global scope across requests.

    """

    def __init__(self, message: dict, journey: str = None):
        self.user_id = message.get("user_id")
        self.channel_slug = message.get("channel_slug")
        if not self.user_id:
            err = "An Angelia Background message exception user_id was not sent"
            logger.error(err)
            raise ValueError(err)
        if not self.channel_slug:
            err = "An Angelia Background message exception channel_slug was not sent"
            logger.error(err)
            raise ValueError(err)
        self.history_kwargs = {
            "user_info": user_info(user_id=self.user_id, channel=self.channel_slug),
        }
        if journey:
            self.history_kwargs["journey"] = journey
        set_history_kwargs(self.history_kwargs)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        clean_history_kwargs(self.history_kwargs)
        if exc_value:
            # Handle Error...
            logger.exception(
                f"An Angelia Background exception occurred in block: {exc_type}," f" Exception message: {exc_value}"
            )
            return True


def credentials_to_key_pairs(cred_list: list) -> dict:
    ret = {}
    for item in cred_list:
        ret[item["credential_slug"]] = item["value"]
    return ret


def set_auth_provided(scheme_account: SchemeAccount, user_id: int, new_value: bool) -> None:
    link = SchemeAccountEntry.objects.get(scheme_account_id=scheme_account.id, user_id=user_id)
    link.auth_provided = new_value
    link.save(update_fields=["auth_provided"])


def post_payment_account(message: dict) -> None:
    # Calls Metis to enrol payment card if account was just created.
    logger.info("Handling onward POST/payment_account journey from Angelia. ")
    with AngeliaContext(message) as ac:
        payment_card_account = PaymentCardAccount.objects.get(pk=message.get("payment_account_id"))
        user = CustomUser.objects.get(pk=ac.user_id)
        if message.get("auto_link"):
            AutoLinkOnCreationMixin.auto_link_to_membership_cards(
                user, payment_card_account, ac.channel_slug, just_created=True
            )
        if message.get("created"):
            metis.enrol_new_payment_card(payment_card_account, run_async=False)


def delete_payment_account(message: dict) -> None:
    logger.info("Handling DELETE/payment_account journey from Angelia.")
    with AngeliaContext(message) as ac:
        query = {"user_id": ac.user_id, "payment_card_account_id": message["payment_account_id"]}
        get_object_or_404(PaymentCardAccountEntry.objects, **query).delete()
        deleted_payment_card_cleanup(payment_card_id=message["payment_account_id"], payment_card_hash=None)


def loyalty_card_register(message: dict) -> None:
    logger.info("Handling loyalty_card REGISTER journey")
    _loyalty_card_register(message, path=LoyaltyCardPath.REGISTER)


def loyalty_card_add_and_register(message: dict) -> None:
    logger.info("Handling loyalty_card ADD and REGISTER journey")
    _loyalty_card_register(message, path=LoyaltyCardPath.ADD_AND_REGISTER)


def _loyalty_card_register(message: dict, path: str) -> None:
    with AngeliaContext(message, SchemeAccountJourney.REGISTER.value) as ac:
        all_credentials_and_consents = {}
        all_credentials_and_consents.update(credentials_to_key_pairs(message.get("register_fields")))

        if message.get("consents"):
            all_credentials_and_consents.update({"consents": message["consents"]})

        user = CustomUser.objects.get(pk=ac.user_id)
        permit = Permit(bundle_id=ac.channel_slug, user=user)
        account = SchemeAccount.objects.get(pk=message.get("loyalty_card_id"))
        sch_acc_entry = account.schemeaccountentry_set.get(user=user)
        scheme = account.scheme
        questions = scheme.questions.all()

        if path == LoyaltyCardPath.REGISTER:
            register_lc_event(user, account, ac.channel_slug)

        if message.get("auto_link"):
            payment_cards_to_link = PaymentCardAccountEntry.objects.filter(user_id=user.id).values_list(
                "payment_card_account_id", flat=True
            )
            if payment_cards_to_link:
                auto_link_membership_to_payments(payment_cards_to_link=payment_cards_to_link, membership_card=account)
        MembershipCardView._handle_registration_route(
            user=user,
            permit=permit,
            scheme_acc_entry=sch_acc_entry,
            scheme_questions=questions,
            registration_fields=all_credentials_and_consents,
            scheme=scheme,
            account=account,
        )


def loyalty_card_add_authorise(message: dict) -> None:
    with AngeliaContext(message) as ac:
        journey = message.get("journey")

        if message.get("auto_link"):
            payment_cards_to_link = PaymentCardAccountEntry.objects.filter(user_id=ac.user_id).values_list(
                "payment_card_account_id", flat=True
            )
        else:
            payment_cards_to_link = []

        all_credentials_and_consents = {}
        all_credentials_and_consents.update(credentials_to_key_pairs(message.get("authorise_fields")))

        if message.get("consents"):
            all_credentials_and_consents.update({"consents": message["consents"]})

        account = SchemeAccount.objects.get(pk=message.get("loyalty_card_id"))

        set_auth_provided(account, ac.user_id, True)

        if message.get("primary_auth"):
            # primary_auth is used to indicate that this user has demonstrated the authority to authorise and
            # set the status of this card (i.e. they are not secondary to an authorised user of this card.)
            if journey == "ADD_AND_AUTH":
                account.set_add_auth_pending()
            elif journey == "AUTH":
                account.set_auth_pending()

            async_link(
                auth_fields=all_credentials_and_consents,
                scheme_account_id=account.id,
                user_id=ac.user_id,
                payment_cards_to_link=payment_cards_to_link,
            )

        if payment_cards_to_link:
            # if the request does not come from a primary_auth, then we will just auto-link this user's
            # cards without affecting the state of the loyalty card.
            auto_link_membership_to_payments(payment_cards_to_link=payment_cards_to_link, membership_card=account)


def loyalty_card_join(message: dict) -> None:
    logger.info("Handling loyalty_card join")
    with AngeliaContext(message, SchemeAccountJourney.ENROL.value) as ac:
        if message.get("auto_link"):
            payment_cards_to_link = PaymentCardAccountEntry.objects.filter(user_id=ac.user_id).values_list(
                "payment_card_account_id", flat=True
            )
        else:
            payment_cards_to_link = []

        all_credentials_and_consents = credentials_to_key_pairs(message.get("join_fields"))

        if message.get("consents"):
            all_credentials_and_consents.update({"consents": message["consents"]})

        user = CustomUser.objects.get(pk=ac.user_id)
        account = SchemeAccount.objects.get(pk=message.get("loyalty_card_id"))
        scheme = Scheme.objects.get(pk=message.get("loyalty_plan_id"))
        permit = Permit(bundle_id=ac.channel_slug, user=user)

        validated_data, serializer, _ = SchemeAccountJoinMixin.validate(
            data=all_credentials_and_consents,
            scheme_account=account,
            user=user,
            permit=permit,
            join_scheme=scheme,
        )

        # send event to data warehouse
        join_request_lc_event(user, account, ac.channel_slug)

        async_join(
            scheme_account_id=account.id,
            user_id=user.id,
            serializer=serializer,
            scheme_id=scheme.id,
            validated_data=validated_data,
            channel=ac.channel_slug,
            payment_cards_to_link=payment_cards_to_link,
        )


def delete_loyalty_card(message: dict) -> None:
    with AngeliaContext(message) as ac:
        user = CustomUser.objects.get(pk=ac.user_id)
        account = SchemeAccount.objects.get(pk=message.get("loyalty_card_id"))
        SchemeAccountEntry.objects.filter(scheme_account=account, user=user).delete()
        deleted_membership_card_cleanup(account.id, arrow.utcnow().format(), user.id)


def delete_user(message: dict) -> None:
    consent_data = None
    with AngeliaContext(message) as ac:
        try:
            user = CustomUser.objects.get(pk=ac.user_id)
        except CustomUser.DoesNotExist:
            logger.exception(f"Could not delete user {ac.user_id} - account not found.")
        else:
            try:
                consent = ServiceConsent.objects.get(pk=ac.user_id)
                consent_data = {"email": user.email, "timestamp": consent.timestamp}
            except ServiceConsent.DoesNotExist:
                logger.exception(f"Service Consent data could not be found whilst deleting user {ac.user_id} .")
            user.soft_delete()
            deleted_service_cleanup(user_id=ac.user_id, consent=consent_data)
            logger.info(f"User {ac.user_id} successfully deleted. ")


def refresh_balances(message: dict) -> None:
    with AngeliaContext(message) as ac:
        user = CustomUser.objects.get(pk=ac.user_id)
        permit = Permit(bundle_id=ac.channel_slug, user=user)
        async_all_balance(ac.user_id, permit)
        logger.info(f"User {ac.user_id} refresh balances called. ")


table_to_model = {
    "user": "CustomUser",
    "scheme_schemeaccount": "SchemeAccount",
    "ubiquity_schemeaccountentry": "SchemeAccountEntry",
    "ubiquity_paymentcardschemeentry": "PaymentCardSchemeEntry",
    "payment_card_paymentcardaccount": "PaymentCardAccount",
    "ubiquity_paymentcardaccountentry": "PaymentCardAccountEntry",
    "ubiquity_vopactivation": "VopActivation",
}

journey_map = (
    SchemeAccountJourney.ENROL.value,
    SchemeAccountJourney.NONE.value,
    SchemeAccountJourney.ADD.value,
    SchemeAccountJourney.NONE.value,
    SchemeAccountJourney.REGISTER.value,
    SchemeAccountJourney.NONE.value,
)


class FakeRelatedModel:
    """We can't pass a model from Angelia in mapper_history message.
    However, Rest Serializer in Hermes uses a class PKOnlyObject: which they say
    is a mock object, used for when we only need the pk of the object.
    This FakeRelatedModel reconstructs an object from the id so that it can
    be serialised.  This was originally required for PaymentCard field when
    updating PaymentCard on Angelia
    """

    def __init__(self, object_id):
        self.pk = object_id


def record_mapper_history(model_name: str, ac: AngeliaContext, message: dict):
    payload = message.get("payload", {})
    related = message.get("related", {})
    change_details = message.get("change", "")
    for rk, ri in related.items():
        if ri:
            payload[rk] = FakeRelatedModel(ri)
        else:
            payload[rk] = None

    extra = {"user_id": ac.user_id, "channel": ac.channel_slug}
    event_time = datetime.strptime(message["event_date"], "%Y-%m-%dT%H:%M:%S.%fZ")
    required_extra_fields = get_required_extra_fields(model_name)

    if "body" in required_extra_fields:
        extra["body"] = get_body_serializer(model_name)(payload).data

    if "journey" in required_extra_fields:
        if message["event"] == "create" and payload.get("originating_journey", -1) <= 5:
            extra["journey"] = journey_map[payload["originating_journey"]]

    for field in required_extra_fields:
        if field not in extra and payload.get(field):
            extra[field] = payload[field]

    record_history(
        model_name,
        event_time=event_time,
        change_type=message["event"],
        change_details=change_details,
        instance_id=payload.get("id", None),
        **extra,
    )


def mapper_history(message: dict) -> None:
    """This message assumes Angelia logged history via mapper database event ie an ORM based where the
    data was know to Angelia and can be passed to Hermes to update History
    """
    model_name = table_to_model.get(message.get("table", ""), False)
    if message.get("payload") and model_name:
        with AngeliaContext(message) as ac:
            record_mapper_history(model_name, ac, message)
    else:
        logger.error(f"Failed to process history entry for {model_name}")


def add_auth_outcome_event(message: dict) -> None:
    success = message.get("success")
    journey = message.get("journey")
    user_id = message.get("user_id")
    loyalty_card_id = message.get("loyalty_card_id")

    # build user and scheme_account objects...
    user = CustomUser.objects.get(id=user_id)
    scheme_account = SchemeAccount.objects.get(pk=loyalty_card_id)

    if journey == "ADD_AND_AUTH":
        add_auth_outcome(success=success, user=user, scheme_account=scheme_account)
    elif journey == "AUTH":
        auth_outcome(success=success, user=user, scheme_account=scheme_account)


def add_auth_request_event(message: dict) -> None:
    journey = message.get("journey")
    user_id = message.get("user_id")
    loyalty_card_id = message.get("loyalty_card_id")
    channel_slug = message.get("channel_slug")
    user = CustomUser.objects.get(id=user_id)
    scheme_account = SchemeAccount.objects.get(pk=loyalty_card_id)

    if journey == "ADD_AND_AUTH":
        add_and_auth_lc_event(user, scheme_account, channel_slug)
    elif journey == "AUTH":
        auth_request_lc_event(user, scheme_account, channel_slug)


def sql_history(message: dict) -> None:
    """This message assumes Angelia logged history via sql and no event was raised ie the model data
    was not know to Angelia because a SqlAlchemy mapped the Model to the table name and then sent a SQL to
    postgres which did not
    """
    with AngeliaContext(message) as ac:
        event_time = datetime.strptime(message["event_date"], "%Y-%m-%dT%H:%M:%S.%fZ")
        model_name = table_to_model.get(message.get("table", ""), False)

        if model_name == "CustomUser":
            # This relates to user update add paths is via mapper
            user = CustomUser.objects.get(id=ac.user_id)
            serializer = HistoryUserSerializer(user)
            record_history(
                model_name,
                event_time=event_time,
                change_type=message["event"],
                change_details=message["change"],
                channel=ac.channel_slug,
                instance_id=message["id"],
                email=user.email,
                external_id=user.external_id,
                body=serializer.data,
            )
