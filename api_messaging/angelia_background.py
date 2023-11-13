import logging
from enum import Enum

from rest_framework.exceptions import ValidationError as RestValidationError
from rest_framework.generics import get_object_or_404
from rest_framework.settings import api_settings

from hermes.channels import Permit
from hermes.utils import ctx
from history.data_warehouse import (
    add_trusted_lc_event,
    addauth_request_lc_event,
    auth_request_lc_event,
    join_outcome,
    join_request_lc_event,
    register_lc_event,
    to_data_warehouse,
)
from history.enums import SchemeAccountJourney
from history.models import get_required_extra_fields
from history.serializers import get_body_serializer
from history.tasks import add_auth_outcome_task, auth_outcome_task, record_history
from history.utils import clean_history_kwargs, set_history_kwargs, user_info
from payment_card import metis
from payment_card.models import PaymentCardAccount
from scheme.credentials import MERCHANT_IDENTIFIER
from scheme.mixins import SchemeAccountJoinMixin
from scheme.models import Scheme, SchemeAccount, SchemeAccountCredentialAnswer
from ubiquity.models import (
    AccountLinkStatus,
    PaymentCardAccountEntry,
    PllUserAssociation,
    SchemeAccountEntry,
    ServiceConsent,
)
from ubiquity.tasks import (  # auto_link_membership_to_payments,
    async_all_balance,
    async_join,
    async_link,
    auto_link_payment_to_memberships,
    deleted_membership_card_cleanup,
    deleted_payment_card_cleanup,
    deleted_service_cleanup,
)
from ubiquity.views import MembershipCardView
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

    def __init__(self, message: dict, journey: str | None = None):
        self.user_id = message.get("user_id")
        self.channel_slug = message.get("channel_slug")
        self.entry_id = message.get("entry_id")
        self.add_fields = message.get("add_fields")
        self.date_time = message.get("utc_adjusted")
        # auto_link was only sent for payment and not membership cards. Now use self.auto_link as it is True by default
        # ie unless a message with specific entry auto_link=False must be sent
        self.auto_link = message.get("auto_link", True)
        if not self.user_id:
            err = "An Angelia Background message exception user_id was not sent"
            logger.error(err)
            raise ValueError(err)
        if not self.channel_slug:
            err = "An Angelia Background message exception channel_slug was not sent"
            logger.error(err)
            raise ValueError(err)
        if not self.date_time:
            err = "An Angelia Background message exception utc_adjusted was not sent"
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
        if exc_type:
            logger.exception("Error occurred when processing Angelia background task")


def credentials_to_key_pairs(cred_list: list) -> dict:
    ret = {}
    for item in cred_list:
        ret[item["credential_slug"]] = item["value"]
    return ret


# @todo we must use API method of linking here:
def post_payment_account(message: dict, headers: dict) -> None:
    # Calls Metis to enrol payment card if account was just created.
    logger.info("Handling onward POST/payment_account journey from Angelia. ")
    with AngeliaContext(message) as ac:
        ctx.x_azure_ref = headers.get("X-azure-ref")
        payment_card_account = PaymentCardAccount.all_objects.get(pk=message.get("payment_account_id"))
        user = CustomUser.objects.get(pk=ac.user_id)
        # auto_link
        if ac.auto_link:
            # @todo - Do we must use PllUserAssociation for API 2.0 - done now - remove comment when ready
            # Linking before enrolment is ok because it ensures the pending states are set up with
            # a good chance of being ready when the new card goes active.
            # AutoLinkOnCreationMixin.auto_link_to_membership_cards(
            # user, payment_card_account, ac.channel_slug, just_created=True
            # )
            auto_link_payment_to_memberships(
                payment_card_account=payment_card_account,
                user_id=user.id,
                just_created=True,  # The card may already exist in another wallet but it's just created in that it
                # needs linking as if a new card
                history_kwargs={"user_info": user_info(user_id=user.id, channel=ac.channel_slug)},
                headers=headers,
            )

        if message.get("created"):
            # For when adding a previously deleted card. Unique logic required for MasterCard.
            if message.get("supersede"):
                metis.enrol_existing_payment_card(payment_card_account, run_async=False, headers=headers)
            else:
                metis.enrol_new_payment_card(payment_card_account, run_async=False, headers=headers)


# @todo we must use API method of linking here:
def delete_payment_account(message: dict, headers: dict) -> None:
    logger.info("Handling DELETE/payment_account journey from Angelia.")
    with AngeliaContext(message) as ac:
        ctx.x_azure_ref = headers.get("X-azure-ref")
        query = {"user_id": ac.user_id, "payment_card_account_id": message["payment_account_id"]}
        get_object_or_404(PaymentCardAccountEntry.objects, **query).delete()
        deleted_payment_card_cleanup(
            payment_card_id=message["payment_account_id"],
            payment_card_hash=None,
            user_id=ac.user_id,
            channel_slug=ac.channel_slug,
        )


def loyalty_card_register(message: dict, headers: dict) -> None:
    logger.info("Handling loyalty_card REGISTER journey")
    _loyalty_card_register(message, path=LoyaltyCardPath.REGISTER, headers=headers)


def loyalty_card_add_and_register(message: dict, headers: dict) -> None:
    logger.info("Handling loyalty_card ADD and REGISTER journey")
    _loyalty_card_register(message, path=LoyaltyCardPath.ADD_AND_REGISTER, headers=headers)


def link_payment_cards(
    user_id: int, scheme_account_entry: SchemeAccountEntry, auto_link: bool = True, headers: dict | None = None
):
    if auto_link:
        payment_cards_to_link = PaymentCardAccountEntry.objects.filter(user_id=user_id).values_list(
            "payment_card_account_id", flat=True
        )
        if payment_cards_to_link:
            PllUserAssociation.link_users_payment_cards(scheme_account_entry, payment_cards_to_link, headers=headers)


def _loyalty_card_register(message: dict, path: LoyaltyCardPath, headers: dict) -> None:
    with AngeliaContext(message, SchemeAccountJourney.REGISTER.value) as ac:
        ctx.x_azure_ref = headers.get("X-azure-ref")
        all_credentials_and_consents = {}
        all_credentials_and_consents.update(credentials_to_key_pairs(message.get("register_fields")))

        if message.get("consents"):
            all_credentials_and_consents.update({"consents": message["consents"]})

        user = CustomUser.objects.get(pk=ac.user_id)
        permit = Permit(bundle_id=ac.channel_slug, user=user)
        account = SchemeAccount.objects.get(pk=message.get("loyalty_card_id"))
        scheme = account.scheme
        questions = scheme.questions.all()

        scheme_account_entry = SchemeAccountEntry.objects.get(pk=ac.entry_id)

        if path in [LoyaltyCardPath.REGISTER, LoyaltyCardPath.ADD_AND_REGISTER]:
            register_lc_event(scheme_account_entry, ac.channel_slug, ac.date_time, headers=headers)

        link_payment_cards(ac.user_id, scheme_account_entry, ac.auto_link, headers=headers)
        """
        if message.get("auto_link"):
            payment_cards_to_link = PaymentCardAccountEntry.objects.filter(user_id=user.id).values_list(
                "payment_card_account_id", flat=True
            )
            if payment_cards_to_link:
                PllUserAssociation.link_users_payment_cards(scheme_account_entry, payment_cards_to_link)
                # auto_link_membership_to_payments(payment_cards_to_link=payment_cards_to_link, membership_card=account)
        """

        MembershipCardView.handle_registration_route(
            user=user,
            permit=permit,
            scheme_acc_entry=scheme_account_entry,
            scheme_questions=questions,
            registration_fields=all_credentials_and_consents,
            scheme=scheme,
            headers=headers,
        )


def loyalty_card_add(message: dict, headers: dict) -> None:
    with AngeliaContext(message) as ac:
        ctx.x_azure_ref = headers.get("X-azure-ref")
        scheme_account_entry = SchemeAccountEntry.objects.get(pk=ac.entry_id)
        link_payment_cards(ac.user_id, scheme_account_entry, ac.auto_link, headers=headers)
        create_key_credential_from_add_fields(scheme_account_entry=scheme_account_entry, add_fields=ac.add_fields)


def loyalty_card_trusted_add(message: dict, headers: dict) -> None:
    with AngeliaContext(message) as ac:
        ctx.x_azure_ref = headers.get("X-azure-ref")
        scheme_account_id = message.get("loyalty_card_id")
        scheme_account_entry = SchemeAccountEntry.objects.select_related("scheme_account").get(
            user=ac.user_id, scheme_account_id=scheme_account_id, scheme_account__is_deleted=False
        )
        link_payment_cards(ac.user_id, scheme_account_entry, ac.auto_link, headers=headers)
        create_key_credential_from_add_fields(scheme_account_entry=scheme_account_entry, add_fields=ac.add_fields)

        for credential in message.get("merchant_fields"):
            cred_type = credential["credential_slug"]
            answer = credential["value"]
            question = scheme_account_entry.scheme_account.scheme.questions.get(type=cred_type)

            SchemeAccountCredentialAnswer.objects.update_or_create(
                scheme_account_entry=scheme_account_entry,
                question=question,
                defaults={"answer": answer},
            )

            """
            payment_cards_to_link = PaymentCardAccountEntry.objects.filter(user_id=ac.user_id).values_list(
                "payment_card_account_id", flat=True
            )
            if payment_cards_to_link:
                PllUserAssociation.link_user_scheme_account_to_payment_cards(
                    scheme_account_id, payment_cards_to_link, ac.user_id
                )
            """

        scheme_account_entry.update_scheme_account_key_credential_fields()


def loyalty_card_trusted_add_success_event(message: dict, headers: dict) -> None:
    with AngeliaContext(message) as ac:
        date_time = message.get("utc_adjusted")
        loyalty_card_id = message.get("loyalty_card_id")
        scheme_account = SchemeAccount.objects.get(pk=loyalty_card_id)
        scheme_account_entry = SchemeAccountEntry.objects.get(pk=ac.entry_id) if ac.entry_id else None
        status = scheme_account_entry.link_status if scheme_account_entry else "ACTIVE"
        channel_slug = message.get("channel_slug")
        user = CustomUser.objects.get(id=ac.user_id)
        add_trusted_lc_event(user, scheme_account, channel_slug, status, date_time, headers)


def loyalty_card_add_authorise(message: dict, headers: dict) -> None:
    with AngeliaContext(message) as ac:
        ctx.x_azure_ref = headers.get("X-azure-ref")
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
        scheme_account_entry = SchemeAccountEntry.objects.get(pk=ac.entry_id)

        if journey == "ADD_AND_AUTH":
            create_key_credential_from_add_fields(scheme_account_entry=scheme_account_entry, add_fields=ac.add_fields)
            scheme_account_entry.set_link_status(AccountLinkStatus.ADD_AUTH_PENDING)
        elif journey == "AUTH":
            scheme_account_entry.schemeaccountcredentialanswer_set.filter(
                question__type=MERCHANT_IDENTIFIER,
            ).delete()
            scheme_account_entry.set_link_status(AccountLinkStatus.AUTH_PENDING, commit_change=False)
            update_fields = ["link_status"]

            if scheme_account_entry.authorised:
                scheme_account_entry.authorised = False
                update_fields.append("authorised")

            scheme_account_entry.save(update_fields=update_fields)

        async_link(
            auth_fields=all_credentials_and_consents,
            scheme_account_id=account.id,
            user_id=ac.user_id,
            payment_cards_to_link=payment_cards_to_link,
            headers=headers,
        )


def loyalty_card_join(message: dict, headers: dict) -> None:
    logger.info("Handling loyalty_card join")
    with AngeliaContext(message, SchemeAccountJourney.ENROL.value) as ac:
        ctx.x_azure_ref = headers.get("X-azure-ref")
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
        entry = SchemeAccountEntry.objects.get(scheme_account=account, user=user)
        scheme = Scheme.objects.get(pk=message.get("loyalty_plan_id"))
        permit = Permit(bundle_id=ac.channel_slug, user=user)

        try:
            validated_data, serializer, _ = SchemeAccountJoinMixin.validate(
                data=all_credentials_and_consents,
                scheme_account=account,
                user=user,
                permit=permit,
                join_scheme=scheme,
            )
        except RestValidationError as e:
            link_error = AccountLinkStatus.UNKNOWN_ERROR
            if isinstance(e.detail, dict):
                if api_settings.NON_FIELD_ERRORS_KEY not in e.detail.keys():
                    link_error = AccountLinkStatus.INVALID_CREDENTIALS
            entry.set_link_status(link_error)
            if payment_cards_to_link:
                PllUserAssociation.link_user_scheme_account_to_payment_cards(
                    account, payment_cards_to_link, user, headers
                )
            # send event to data warehouse
            join_request_lc_event(entry, ac.channel_slug, ac.date_time, headers=headers)
            # @todo we may need to modify join_outcome to accept a different origin as it is not "merchant call back"
            # however need to agree this with data team.
            join_outcome(
                success=False, scheme_account_entry=entry, date_time=None, headers=headers
            )  # outcome must have now time
        else:
            # send event to data warehouse
            join_request_lc_event(entry, ac.channel_slug, ac.date_time, headers=headers)
            async_join(
                scheme_account_id=account.id,
                user_id=user.id,
                serializer=serializer,
                scheme_id=scheme.id,
                validated_data=validated_data,
                channel=ac.channel_slug,
                payment_cards_to_link=payment_cards_to_link,
                headers=headers,
            )


def delete_loyalty_card(message: dict, headers: dict) -> None:
    with AngeliaContext(message) as ac:
        ctx.x_azure_ref = headers.get("X-azure-ref")
        scheme_account_entry = SchemeAccountEntry.objects.prefetch_related(
            "scheme_account", "scheme_account__scheme", "user", "user__client"
        ).get(scheme_account_id=message.get("loyalty_card_id"), user_id=ac.user_id)
        deleted_membership_card_cleanup(
            scheme_account_entry, ac.date_time, channel_slug=ac.channel_slug, headers=headers
        )


def delete_user(message: dict, headers: dict) -> None:
    consent_data = {}
    with AngeliaContext(message) as ac:
        ctx.x_azure_ref = headers.get("X-azure-ref")
        try:
            user = CustomUser.all_objects.get(pk=ac.user_id)
        except CustomUser.DoesNotExist:
            logger.exception(f"Could not delete user {ac.user_id} - account not found.")
        else:
            try:
                consent = ServiceConsent.objects.get(pk=ac.user_id)
                consent_data = {"email": user.email, "timestamp": consent.timestamp}
            except ServiceConsent.DoesNotExist:
                logger.error(f"Service Consent data could not be found whilst deleting user {ac.user_id} .")

            if user.is_active:
                user.soft_delete()
                msg = f"User {ac.user_id} successfully deleted."
            else:
                msg = f"User {ac.user_id} already deleted, but delete cleanup has run successfully"

            deleted_service_cleanup(
                user_id=ac.user_id, consent=consent_data, channel_slug=ac.channel_slug, headers=headers
            )
            logger.info(msg)


def refresh_balances(message: dict, headers: dict) -> None:
    with AngeliaContext(message) as ac:
        ctx.x_azure_ref = headers.get("X-azure-ref")
        user = CustomUser.objects.get(pk=ac.user_id)
        permit = Permit(bundle_id=ac.channel_slug, user=user)
        async_all_balance(ac.user_id, permit, headers=headers)
        logger.info(f"User {ac.user_id} refresh balances called. ")


def user_session(message: dict, headers: dict) -> None:
    ctx.x_azure_ref = headers.get("X-azure-ref")
    user = CustomUser.objects.get(id=message.get("user_id"))
    user.last_accessed = message.get("utc_adjusted")
    user.save(update_fields=["last_accessed"])
    payload = {
        "event_type": "user.session.start",
        "origin": "channel",
        "channel": message.get("channel_slug"),
        "event_date_time": user.last_accessed,
        "external_user_ref": user.external_id,
        "internal_user_ref": user.id,
        "email": user.email,
    }
    to_data_warehouse(payload, headers)


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


def record_mapper_history(model_name: str, ac: AngeliaContext, message: dict, headers: dict | None = None):
    payload = message.get("payload", {})
    related = message.get("related", {})
    change_details = message.get("change", "")
    for rk, ri in related.items():
        if ri:
            payload[rk] = FakeRelatedModel(ri)
        else:
            payload[rk] = None

    extra = {"user_id": ac.user_id, "channel": ac.channel_slug}
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
        headers,
        event_time=ac.date_time,
        change_type=message["event"],
        change_details=change_details,
        instance_id=payload.get("id", None),
        **extra,
    )


def mapper_history(message: dict, headers: dict) -> None:
    """This message assumes Angelia logged history via mapper database event ie an ORM based where the
    data was known to Angelia and can be passed to Hermes to update History
    """
    model_name = table_to_model.get(message.get("table", ""), False)
    ctx.x_azure_ref = headers.get("X-azure-ref")
    if message.get("payload") and model_name:
        with AngeliaContext(message) as ac:
            record_mapper_history(model_name, ac, message, headers)
    else:
        logger.error(f"Failed to process history entry for {model_name}")


def add_auth_outcome_event(message: dict, headers: dict) -> None:
    ctx.x_azure_ref = headers.get("X-azure-ref")
    success = message.get("success")
    journey = message.get("journey")
    date_time = message.get("utc_adjusted")
    scheme_account_entry = SchemeAccountEntry.objects.get(pk=message.get("entry_id"))

    if journey == "ADD_AND_AUTH":
        add_auth_outcome_task(
            success=success, scheme_account_entry=scheme_account_entry, date_time=date_time, headers=headers
        )
    elif journey == "AUTH":
        auth_outcome_task(
            success=success, scheme_account_entry=scheme_account_entry, date_time=date_time, headers=headers
        )


def add_auth_request_event(message: dict, headers: dict) -> None:
    ctx.x_azure_ref = headers.get("X-azure-ref")
    journey = message.get("journey")
    user_id = message.get("user_id")
    date_time = message.get("utc_adjusted")
    loyalty_card_id = message.get("loyalty_card_id")
    channel_slug = message.get("channel_slug")
    user = CustomUser.objects.get(id=user_id)
    scheme_account = SchemeAccount.objects.get(pk=loyalty_card_id)

    if journey == "ADD_AND_AUTH":
        addauth_request_lc_event(user, scheme_account, channel_slug, date_time, headers)
    elif journey == "AUTH":
        auth_request_lc_event(user, scheme_account, channel_slug, date_time, headers)


def sql_history(message: dict, headers: dict) -> None:
    """This message assumes Angelia logged history via sql and no event was raised ie the model data
    was not know to Angelia because a SqlAlchemy mapped the Model to the table name and then sent a SQL to
    postgres which did not
    """
    ctx.x_azure_ref = headers.get("X-azure-ref")
    with AngeliaContext(message) as ac:
        model_name = table_to_model.get(message.get("table", ""), False)

        if model_name == "CustomUser":
            # This relates to user update add paths is via mapper
            user = CustomUser.objects.get(id=ac.user_id)
            serializer = HistoryUserSerializer(user)
            record_history(
                model_name,
                headers,
                event_time=ac.date_time,
                change_type=message["event"],
                change_details=message["change"],
                channel=ac.channel_slug,
                instance_id=message["id"],
                email=user.email,
                external_id=user.external_id,
                body=serializer.data,
            )


def create_key_credential_from_add_fields(scheme_account_entry: SchemeAccountEntry, add_fields):
    cred_type = add_fields[0]["credential_slug"]
    answer = add_fields[0]["value"]

    question = scheme_account_entry.scheme_account.scheme.questions.get(type=cred_type)

    SchemeAccountCredentialAnswer.objects.update_or_create(
        scheme_account_entry=scheme_account_entry,
        question=question,
        defaults={"answer": answer},
    )
