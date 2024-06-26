import logging
import re
import typing as t

import arrow
import sentry_sdk
from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.http import HttpRequest, HttpResponseForbidden
from rest_framework import status
from rest_framework.exceptions import NotFound, ParseError, ValidationError
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_201_CREATED
from rest_framework.viewsets import GenericViewSet, ModelViewSet
from rustyjeff import rsa_decrypt_base64
from shared_config_storage.credentials.encryption import BLAKE2sHash
from shared_config_storage.credentials.utils import AnswerTypeChoices

from hermes.channels import Permit
from hermes.settings import Version
from history.data_warehouse import (
    addauth_request_lc_event,
    auth_request_lc_event,
    join_request_lc_event,
    register_lc_event,
)
from history.enums import SchemeAccountJourney
from history.signals import HISTORY_CONTEXT
from history.utils import user_info
from payment_card.enums import PaymentCardRoutes
from payment_card.models import PaymentCardAccount
from payment_card.payment import get_nominated_pcard
from payment_card.views import ListCreatePaymentCardAccount, RetrievePaymentCardAccount
from prometheus.metrics import (
    MembershipCardAddRoute,
    PaymentCardAddRoute,
    membership_card_add_counter,
    membership_card_update_counter,
    payment_card_add_counter,
    service_creation_counter,
)
from scheme.credentials import EMAIL, PAYMENT_CARD_HASH
from scheme.mixins import (
    BaseLinkMixin,
    IdentifyCardMixin,
    SchemeAccountCreationMixin,
    SchemeAccountJoinMixin,
    UpdateCredentialsMixin,
)
from scheme.models import JourneyTypes, Scheme, SchemeAccount, SchemeCredentialQuestion, ThirdPartyConsentLink
from scheme.views import RetrieveDeleteAccount
from ubiquity.authentication import PropertyAuthentication, PropertyOrServiceAuthentication
from ubiquity.cache_decorators import CacheApiRequest, membership_plan_key
from ubiquity.censor_empty_fields import censor_and_decorate
from ubiquity.channel_vault import KeyType, SecretKeyName, get_bundle_key, get_secret_key
from ubiquity.exceptions import AlreadyExistsError, CardAuthError
from ubiquity.influx_audit import audit
from ubiquity.models import (
    AccountLinkStatus,
    PaymentCardAccountEntry,
    PaymentCardSchemeEntry,
    PllUserAssociation,
    SchemeAccountEntry,
    ServiceConsent,
    VopActivation,
)
from ubiquity.tasks import (
    async_all_balance,
    async_balance_with_updated_credentials,
    async_join,
    async_link,
    async_registration,
    auto_link_payment_to_memberships,
    deleted_membership_card_cleanup,
    deleted_payment_card_cleanup,
    deleted_service_cleanup,
    send_merchant_metrics_for_new_account,
)
from ubiquity.utils import needs_decryption
from ubiquity.versioning import SelectSerializer, get_api_version, versioned_serializer_class
from ubiquity.versioning.base.serializers import (
    LinkMembershipCardSerializer,
    MembershipCardSerializer,
    MembershipPlanSerializer,
    MembershipTransactionsMixin,
    PaymentCardConsentSerializer,
    PaymentCardSerializer,
    PaymentCardUpdateSerializer,
    ServiceSerializer,
    TransactionSerializer,
)
from user.authentication import ServiceAuthentication as InternalServiceAuthentication
from user.models import CustomUser

if t.TYPE_CHECKING:
    from rest_framework.request import Request
    from rest_framework.serializers import Serializer

escaped_unicode_pattern = re.compile(r"\\(\\u[a-fA-F0-9]{4})")
logger = logging.getLogger(__name__)


def auto_link(req):
    auto_link_mapping = {
        "true": True,
        "false": False,
    }
    auto_link_param = req.query_params.get("autolink", "") or req.query_params.get("autoLink", "")

    return auto_link_mapping.get(auto_link_param.lower(), None)


def replace_escaped_unicode(match):
    return match.group(1)


def detect_and_handle_escaped_unicode(credentials_dict):
    # Fix for Barclays sending escaped unicode sequences for special chars in password.
    if credentials_dict.get("password"):
        password = credentials_dict["password"]
        if password.isascii():
            password = escaped_unicode_pattern.sub(replace_escaped_unicode, password).encode().decode("unicode-escape")

        credentials_dict["password"] = password

    return credentials_dict


def check_join_with_pay(enrol_fields: dict, user_id: int):
    payment_card_hash = enrol_fields.get(PAYMENT_CARD_HASH)
    if payment_card_hash:
        try:
            get_nominated_pcard(payment_card_hash, user_id)
        except PaymentCardAccount.DoesNotExist as e:
            raise ParseError(detail="Provided payment card could not be found " "or is not related to this user") from e


class VersionedSerializerMixin:
    @staticmethod
    def get_serializer_by_version(serializer: SelectSerializer, version: "Version", *args, **kwargs) -> "Serializer":
        serializer_class = versioned_serializer_class(version, serializer)
        return serializer_class(*args, **kwargs)

    def get_serializer_by_request(self, *args, **kwargs):
        version = get_api_version(self.request)
        serializer_class = versioned_serializer_class(version, self.response_serializer)
        context = kwargs.get("context", {})
        context.update(self.get_serializer_context())
        kwargs["context"] = context
        return serializer_class(*args, **kwargs)

    def get_serializer_class_by_request(self):
        version = get_api_version(self.request)
        return versioned_serializer_class(version, self.response_serializer)


class AutoLinkOnCreationMixin:
    @staticmethod
    def auto_link_to_membership_cards(
        user: CustomUser, payment_card_account: PaymentCardAccount, bundle_id: str, just_created: bool = False
    ) -> None:
        """


        # Ensure that we only consider membership cards in a user's wallet which can be PLL linked and ensure
        # we get the user link_status for the scheme account
        wallet_scheme_account_entries = SchemeAccountEntry.objects.filter(
            user=user, scheme_account__scheme__tier=Scheme.PLL
        ).all()

        # wallet_scheme_accounts = SchemeAccount.objects.filter(user_set=user, scheme__tier=Scheme.PLL).all()

        if wallet_scheme_account_entries:
            if payment_card_account.status == PaymentCardAccount.ACTIVE:
                auto_link_payment_to_memberships(wallet_scheme_account_entries, payment_card_account, just_created)
            else:
                auto_link_payment_to_memberships.delay(
                    [sa.id for sa in wallet_scheme_account_entries],
                    payment_card_account.id,
                    just_created,
                    history_kwargs={"user_info": user_info(user_id=user.id, channel=bundle_id)},
                )
        """

        auto_link_payment_to_memberships.delay(
            payment_card_account=payment_card_account.id,
            user_id=user.id,
            just_created=just_created,
            history_kwargs={"user_info": user_info(user_id=user.id, channel=bundle_id)},
        )


class PaymentCardCreationMixin:
    @staticmethod
    def _create_payment_card_consent(consent_data: dict, pcard: PaymentCardAccount) -> PaymentCardAccount:
        serializer = PaymentCardConsentSerializer(data=consent_data, many=True)
        serializer.is_valid(raise_exception=True)
        pcard.consents = serializer.validated_data
        pcard.save(update_fields=["consents"])
        return pcard

    @staticmethod
    def _update_payment_card_consent(consent_data: dict, pcard_pk: int) -> None:
        if not consent_data:
            consents = []
        else:
            serializer = PaymentCardConsentSerializer(data=consent_data, many=True)
            serializer.is_valid(raise_exception=True)
            consents = serializer.validated_data

        PaymentCardAccount.objects.filter(pk=pcard_pk).update(consents=consents)

    @staticmethod
    def payment_card_already_exists(
        data: dict, user: CustomUser
    ) -> tuple[PaymentCardAccount | None, PaymentCardRoutes, int]:
        status_code = status.HTTP_201_CREATED
        card = (
            PaymentCardAccount.all_objects.filter(fingerprint=data["fingerprint"])
            .annotate(belongs_to_this_user=Count("user_set", filter=Q(user_set__id=user.id)))
            .order_by("-belongs_to_this_user", "is_deleted", "-created")
            .first()
        )

        if card is None:
            route = PaymentCardRoutes.NEW_CARD
        elif card.is_deleted:
            route = PaymentCardRoutes.DELETED_CARD
        elif card.belongs_to_this_user:
            route = PaymentCardRoutes.ALREADY_IN_WALLET
            status_code = status.HTTP_200_OK
        else:
            route = PaymentCardRoutes.EXISTS_IN_OTHER_WALLET
        return card, route, status_code

    @staticmethod
    def _add_hash(new_hash: str, card: PaymentCardAccount) -> None:
        if new_hash and not card.hash:
            card.hash = new_hash
            card.save(update_fields=["hash"])

    @staticmethod
    def _link_account_to_new_user(account: PaymentCardAccount, user: CustomUser, data: dict) -> None:
        try:
            with transaction.atomic():
                PaymentCardAccountEntry.objects.create(user=user, payment_card_account=account)
                if account.expiry_month != data["expiry_month"] or account.expiry_year != data["expiry_year"]:
                    account.expiry_month = data["expiry_month"]
                    account.expiry_year = data["expiry_year"]
                    account.save(update_fields=["expiry_month", "expiry_year"])
        except IntegrityError:
            pass

    @staticmethod
    def _collect_creation_data(
        request_data: dict, allowed_issuers: list[int], version: "Version", bundle_id: str | None = None
    ) -> tuple[dict, dict]:
        try:
            pcard_data = VersionedSerializerMixin.get_serializer_by_version(
                SelectSerializer.PAYMENT_CARD_TRANSLATION,
                version,
                request_data["card"],
                context={"bundle_id": bundle_id},
            ).data

            if allowed_issuers and pcard_data["issuer"].id not in allowed_issuers:
                raise ParseError("issuer not allowed for this user.")

            consent = request_data["account"]["consents"]
        except (KeyError, ValueError) as e:
            logger.debug(f"error creating payment card: {e!r}")
            raise ParseError from e

        return pcard_data, consent


class AllowedIssuersMixin:
    stored_allowed_issuers = None

    @property
    def allowed_issuers(self):
        if self.stored_allowed_issuers is None:
            self.stored_allowed_issuers = list(self.request.channels_permit.bundle.issuer.values_list("id", flat=True))

        return self.stored_allowed_issuers


class ServiceView(VersionedSerializerMixin, ModelViewSet):
    authentication_classes = (PropertyOrServiceAuthentication,)
    serializer_class = ServiceSerializer
    response_serializer = SelectSerializer.SERVICE

    @censor_and_decorate
    def retrieve(self, request, *args, **kwargs):
        try:
            service_consent = request.user.serviceconsent
        except ServiceConsent.DoesNotExist:
            raise NotFound from None

        async_all_balance.delay(request.user.id, self.request.channels_permit)
        return Response(self.get_serializer_by_request(service_consent).data)

    @censor_and_decorate
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})

        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError:
            # Generic response required for Barclays
            raise ParseError from None

        service_consent, service_consent_created = serializer.save()
        logger.info(f"Service consent retrieved (id={service_consent.pk}) - created: {service_consent_created}")

        status_code = HTTP_200_OK
        if service_consent_created:
            service_creation_counter.labels(channel=request.channels_permit.bundle_id).inc()
            status_code = HTTP_201_CREATED

        consent = self.get_serializer_by_request(service_consent)
        return Response(consent.data, status=status_code)

    @censor_and_decorate
    def destroy(self, request, *args, **kwargs):
        try:
            response = self.get_serializer_by_request(request.user.serviceconsent).data
        except ServiceConsent.DoesNotExist:
            raise NotFound from None

        request.user.soft_delete()
        user_id = request.user.id
        deleted_service_cleanup.delay(
            user_id,
            response["consent"],
            channel_slug=request.channels_permit.bundle_id,
            history_kwargs={"user_info": user_info(user_id=user_id, channel=request.channels_permit.bundle_id)},
        )
        return Response(response)


class PaymentCardView(
    RetrievePaymentCardAccount,
    VersionedSerializerMixin,
    PaymentCardCreationMixin,
    AutoLinkOnCreationMixin,
    AllowedIssuersMixin,
    ModelViewSet,
):
    authentication_classes = (PropertyAuthentication,)
    serializer_class = PaymentCardSerializer
    response_serializer = SelectSerializer.PAYMENT_CARD

    def get_queryset(self):
        query = {}
        if self.allowed_issuers:
            query["issuer__in"] = self.allowed_issuers

        return self.request.channels_permit.payment_card_account_query(
            PaymentCardAccount.objects.filter(**query), user_id=self.request.user.id, user_filter=True
        )

    def get_hashed_object(self):
        if self.kwargs.get("hash"):
            self.kwargs["hash"] = BLAKE2sHash().new(
                obj=self.kwargs["hash"], key=get_secret_key(SecretKeyName.PCARD_HASH_SECRET)
            )
        return super(PaymentCardView, self).get_object()

    @censor_and_decorate
    def retrieve(self, request, *args, **kwargs):
        self.serializer_class = self.get_serializer_class_by_request()
        return super().retrieve(request, *args, **kwargs)

    @censor_and_decorate
    def update(self, request, *args, **kwargs):
        if "card" in request.data:
            try:
                data = PaymentCardUpdateSerializer(request.data["card"]).data
                PaymentCardAccount.objects.filter(pk=kwargs["pk"]).update(**data)
            except ValueError:
                raise ParseError("Invalid card data") from None

        if "account" in request.data and "consents" in request.data["account"]:
            self._update_payment_card_consent(request.data["account"]["consents"], kwargs["pk"])

        pcard = get_object_or_404(PaymentCardAccount, pk=kwargs["pk"])
        return Response(self.get_serializer_by_request(pcard).data)

    @censor_and_decorate
    def replace(self, request, *args, **kwargs):
        account = self.get_object()
        pcard_data, consent = self._collect_creation_data(
            request_data=request.data,
            allowed_issuers=self.allowed_issuers,
            version=get_api_version(request),
            bundle_id=request.channels_permit.bundle_id,
        )
        if pcard_data["fingerprint"] != account.fingerprint:
            raise ParseError("cannot override fingerprint.")

        pcard_data["token"] = account.token
        pcard_data["psp_token"] = account.psp_token
        PaymentCardAccount.objects.filter(pk=account.pk).update(**pcard_data)
        # todo should we replace the consent too?

        account.refresh_from_db()

        if auto_link(request):
            self.auto_link_to_membership_cards(request.user, account, request.channels_permit.bundle_id)

        return Response(self.get_serializer_by_request(account).data, status.HTTP_200_OK)

    @censor_and_decorate
    def destroy(self, request, *args, **kwargs):
        query = {"user_id": request.user.id}
        pcard_hash: str | None = None
        pcard_pk: int | None = None

        if self.kwargs.get("hash"):
            pcard_hash = BLAKE2sHash().new(obj=self.kwargs["hash"], key=get_secret_key(SecretKeyName.PCARD_HASH_SECRET))
            query["payment_card_account__hash"] = pcard_hash
        else:
            pcard_pk = kwargs["pk"]
            query["payment_card_account_id"] = pcard_pk

        get_object_or_404(PaymentCardAccountEntry.objects, **query).delete()
        deleted_payment_card_cleanup.delay(
            pcard_pk,
            pcard_hash,
            request.channels_permit.user.id,
            channel_slug=request.channels_permit.bundle_id,
            history_kwargs={
                "user_info": user_info(
                    user_id=request.channels_permit.user.id, channel=request.channels_permit.bundle_id
                )
            },
        )
        return Response({}, status=status.HTTP_200_OK)


class ListPaymentCardView(
    ListCreatePaymentCardAccount,
    VersionedSerializerMixin,
    PaymentCardCreationMixin,
    AutoLinkOnCreationMixin,
    AllowedIssuersMixin,
    ModelViewSet,
):
    authentication_classes = (PropertyAuthentication,)
    serializer_class = PaymentCardSerializer
    response_serializer = SelectSerializer.PAYMENT_CARD

    def get_queryset(self):
        query = {}
        if self.allowed_issuers:
            query["issuer__in"] = self.allowed_issuers

        return self.request.channels_permit.payment_card_account_query(
            PaymentCardAccount.objects.filter(**query), user_id=self.request.user.id, user_filter=True
        )

    @censor_and_decorate
    def list(self, request, *args, **kwargs):
        accounts = list(self.filter_queryset(self.get_queryset()))
        response = self.get_serializer_by_request(accounts, many=True).data
        return Response(response, status=200)

    @censor_and_decorate
    def create(self, request, *args, **kwargs):
        metrics_route = None
        pcard_data, consent = self._collect_creation_data(
            request_data=request.data,
            allowed_issuers=self.allowed_issuers,
            version=get_api_version(request),
            bundle_id=request.channels_permit.bundle_id,
        )

        # just_created = False
        pcard, route, status_code = self.payment_card_already_exists(pcard_data, request.user)

        if route == PaymentCardRoutes.EXISTS_IN_OTHER_WALLET:
            self._add_hash(pcard_data.get("hash"), pcard)
            self._link_account_to_new_user(pcard, request.user, pcard_data)
            metrics_route = PaymentCardAddRoute.MULTI_WALLET

        elif route in [PaymentCardRoutes.NEW_CARD, PaymentCardRoutes.DELETED_CARD]:
            pcard = self.create_payment_card_account(pcard_data, request.user, pcard)
            self._create_payment_card_consent(consent, pcard)
            # just_created = True

            if route == PaymentCardRoutes.DELETED_CARD:
                metrics_route = PaymentCardAddRoute.RETURNING
            else:
                metrics_route = PaymentCardAddRoute.NEW_CARD

        # auto link to mcards if auto_link is True or None
        if auto_link(request) is not False:
            # just_created must be true to create new links and is not conditional on payment card account already
            # existing
            just_created = True
            self.auto_link_to_membership_cards(request.user, pcard, request.channels_permit.bundle_id, just_created)

        if metrics_route:
            payment_card_add_counter.labels(
                channel=request.channels_permit.bundle_id,
                provider=pcard.payment_card.system_name,
                route=metrics_route.value,
            ).inc()

        return Response(self.get_serializer_by_request(pcard).data, status=status_code)


class MembershipCardView(
    RetrieveDeleteAccount,
    VersionedSerializerMixin,
    UpdateCredentialsMixin,
    BaseLinkMixin,
    SchemeAccountCreationMixin,
    SchemeAccountJoinMixin,
    AutoLinkOnCreationMixin,
    ModelViewSet,
):
    authentication_classes = (PropertyAuthentication,)
    response_serializer = SelectSerializer.MEMBERSHIP_CARD
    override_serializer_classes = {
        "GET": MembershipCardSerializer,
        "PATCH": MembershipCardSerializer,
        "DELETE": MembershipCardSerializer,
        "PUT": LinkMembershipCardSerializer,
    }
    create_update_fields = ("add_fields", "authorise_fields", "registration_fields", "enrol_fields")

    def get_queryset(self):
        return self.request.channels_permit.scheme_account_entry_query(
            SchemeAccountEntry.objects.select_related("scheme_account__scheme").prefetch_related(
                "scheme_account__scheme__schemeoverrideerror_set"
            ),
            user_id=self.request.user.id,
            user_filter=True,
        )

    @censor_and_decorate
    def retrieve(self, request, *args, **kwargs):
        entry = get_object_or_404(self.get_queryset(), scheme_account=self.kwargs["pk"])
        return Response(
            self.get_serializer_by_request(
                entry.scheme_account,
                context={"user_id": self.request.user.id},
            ).data
        )

    def log_update(self, scheme_account_id):
        try:
            request_patch_fields = self.request.data["account"]
            request_fields = {k: [x["column"] for x in v] for k, v in request_patch_fields.items()}
            logger.debug(
                f"Received membership card patch request for scheme account: {scheme_account_id}. "
                f"Requested fields to update: {request_fields}."
            )
        except (KeyError, ValueError, TypeError) as e:
            logger.info(f"Failed to log membership card patch request. Error: {e!r}")

    @censor_and_decorate
    def update(self, request, *args, **kwargs):
        sch_acc_entry = get_object_or_404(self.get_queryset(), scheme_account=self.kwargs["pk"])
        sch_acc_count = SchemeAccountEntry.objects.filter(scheme_account=sch_acc_entry.scheme_account.id).count()
        self.log_update(sch_acc_entry.scheme_account.pk)
        scheme = sch_acc_entry.scheme_account.scheme
        scheme_questions = scheme.questions.all()
        update_fields, registration_fields = self._collect_updated_answers(scheme, scheme_questions)
        send_auth_outcome = False

        if auto_link(request):
            payment_cards_to_link = PaymentCardAccountEntry.objects.filter(user_id=request.user.id).values_list(
                "payment_card_account_id", flat=True
            )
        else:
            payment_cards_to_link = []

        if registration_fields:
            registration_fields = detect_and_handle_escaped_unicode(registration_fields)
            updated_account = self.handle_registration_route(
                request.user,
                sch_acc_entry,
                request.channels_permit,
                scheme,
                registration_fields,
                scheme_questions,
                request.headers,
            )
            metrics_route = MembershipCardAddRoute.REGISTER

            # send this event to data_warehouse
            register_lc_event(sch_acc_entry, request.channels_permit.bundle_id)
        else:
            if sch_acc_count > 1:
                raise CardAuthError(
                    "Cannot update authorise fields for Store type card. Card must be authorised "
                    "via POST /membership_cards endpoint first."
                )

            # send auth request to data warehouse if we see authorise_fields in request data
            # as this is a PATCH_AUTH
            try:
                auth_fields = request.data["account"]["authorise_fields"]
            except (KeyError, TypeError):
                auth_fields = None

            if auth_fields:
                auth_request_lc_event(request.user, sch_acc_entry.scheme_account, request.channels_permit.bundle_id)
                send_auth_outcome = True

            if update_fields:
                update_fields = detect_and_handle_escaped_unicode(update_fields)

            updated_account = self._handle_update_fields(
                update_fields,
                scheme_questions,
                request.user.id,
                sch_acc_entry,
                payment_cards_to_link,
                send_auth_outcome,
            )
            metrics_route = MembershipCardAddRoute.UPDATE

        if metrics_route:
            membership_card_update_counter.labels(
                channel=request.channels_permit.bundle_id, scheme=scheme.slug, route=metrics_route.value
            ).inc()

        return Response(
            self.get_serializer_by_request(
                updated_account,
                context={
                    "user_id": self.request.user.id,
                },
            ).data,
            status=status.HTTP_200_OK,
        )

    def _create_and_link_to_new_account_from_main_answer(
        self, scheme_account_entry: "SchemeAccountEntry", main_answer_field: str, main_answer_value: str
    ):
        # Create a new account and link to this
        new_account = SchemeAccount.objects.create(
            scheme=scheme_account_entry.scheme_account.scheme,
            order=scheme_account_entry.scheme_account.order,
            **{main_answer_field: main_answer_value},
        )

        original_account = scheme_account_entry.scheme_account

        scheme_account_entry.scheme_account = new_account
        scheme_account_entry.save()

        account = new_account

        # Deletes old account if no longer associated with any user
        if not SchemeAccountEntry.objects.filter(scheme_account=original_account).exists():
            original_account.is_deleted = True
            original_account.save(update_fields=["is_deleted"])

            PaymentCardSchemeEntry.objects.filter(scheme_account=original_account).delete()

        scheme_account_entry.update_scheme_account_key_credential_fields()

        return account

    def _handle_update_fields(
        self,
        update_fields: dict,
        scheme_questions: list,
        user_id: int,
        scheme_account_entry: SchemeAccountEntry,
        payment_cards_to_link: list,
        send_auth_outcome: bool = False,
    ) -> SchemeAccount:
        if "consents" in update_fields:
            del update_fields["consents"]

        relink_pll = False
        account = scheme_account_entry.scheme_account

        # todo: We may want to think about what happens if updated credentials match that user's existing credentials.
        #  Do we want to contact Midas in this case?

        # if the credentials contain a main_answer, and this already exists in another account, we block this action.
        main_answer_type = None
        main_answer_field = None  # The lookup field on the scheme account (card_number, barcode, or alt_main_answer)
        main_answer_value = None

        # Will need rework if we allow updating multiple main answers at once
        main_questions = account.scheme.get_required_questions.all()
        main_question_types = [question["type"] for question in main_questions]
        for question_type, value in update_fields.items():
            if question_type in main_question_types:
                main_answer_value = value
                main_answer_type = question_type
                main_answer_field = SchemeAccount.get_key_cred_field_from_question_type(main_answer_type)
                break

        if main_answer_value:
            existing_account = self.get_existing_account_with_same_manual_answer(
                scheme_account=scheme_account_entry.scheme_account,
                scheme_id=scheme_account_entry.scheme_account.scheme.id,
                main_answer=main_answer_value,
                main_answer_field=main_answer_field,
            )

            if existing_account:
                scheme_account_entry.set_link_status(AccountLinkStatus.FAILED_UPDATE)
                return account

        # update credentials
        UpdateCredentialsMixin().update_credentials(
            scheme_account=scheme_account_entry.scheme_account,
            data=update_fields,
            questions=scheme_questions,
            scheme_account_entry=scheme_account_entry,
        )

        if (
            main_answer_type
            and main_answer_field
            and main_answer_value
            != scheme_account_entry.scheme_account.get_key_cred_value_from_question_type(main_answer_type)
        ):
            account = self._create_and_link_to_new_account_from_main_answer(
                scheme_account_entry=scheme_account_entry,
                main_answer_field=main_answer_field,
                main_answer_value=main_answer_value,
            )
            relink_pll = True

        scheme_account_entry.set_link_status(AccountLinkStatus.PENDING)

        # todo: we should be able to replace this with async_balance but will need to consider event handling.
        async_balance_with_updated_credentials.delay(
            instance_id=account.id,
            scheme_account_entry=scheme_account_entry,
            payment_cards_to_link=payment_cards_to_link,
            relink_pll=relink_pll,
            send_auth_outcome=send_auth_outcome,
        )
        return account

    @staticmethod
    def handle_registration_route(
        user: CustomUser,
        scheme_acc_entry: SchemeAccountEntry,
        permit: Permit,
        scheme: Scheme,
        registration_fields: dict,
        scheme_questions: list,
        headers: dict,
    ) -> SchemeAccount:
        journey = SchemeAccountJourney.REGISTER.value
        HISTORY_CONTEXT.journey = journey
        check_join_with_pay(registration_fields, user.id)
        account = scheme_acc_entry.scheme_account
        manual_answer = account.card_number
        if manual_answer:
            main_credential = manual_answer
            question_type = next(question.type for question in scheme_questions if question.manual_question)
        else:
            main_credential = account.barcode
            question_type = next(question.type for question in scheme_questions if question.scan_question)
        registration_data = {question_type: main_credential, **registration_fields, "scheme_account": account}
        validated_data, serializer, _ = SchemeAccountJoinMixin.validate(
            data=registration_data, scheme_account=account, user=user, permit=permit, join_scheme=scheme
        )

        scheme_acc_entry.set_link_status(AccountLinkStatus.REGISTRATION_ASYNC_IN_PROGRESS)

        async_registration.delay(
            user.id,
            serializer,
            account.id,
            validated_data,
            permit.bundle_id,
            history_kwargs={
                "user_info": user_info(user_id=permit.user.id, channel=permit.bundle_id),
                "journey": journey,
            },
            delete_balance=True,
            headers=headers,
        )
        return account

    @censor_and_decorate
    def replace(self, request, *args, **kwargs):
        entry = get_object_or_404(self.get_queryset(), scheme_account=self.kwargs["pk"])

        if auto_link(request):
            payment_cards_to_link = PaymentCardAccountEntry.objects.filter(user_id=request.user.id).values_list(
                "payment_card_account_id", flat=True
            )
        else:
            payment_cards_to_link = []

        if entry.link_status in [
            AccountLinkStatus.PENDING,
            AccountLinkStatus.JOIN_ASYNC_IN_PROGRESS,
            AccountLinkStatus.REGISTRATION_ASYNC_IN_PROGRESS,
        ]:
            raise ParseError("requested card is still in a pending state, please wait for current journey to finish")

        scheme, auth_fields, enrol_fields, add_fields = self._collect_fields_and_determine_route()

        if scheme != entry.scheme_account.scheme:
            raise ParseError(
                "PUT cannot be used to change scheme. Please use POST/membership_cards to create a new "
                "scheme_account instead."
            )

        if not request.channels_permit.is_scheme_available(scheme.id):
            raise ParseError("membership plan not allowed for this user.")

        # This check needs to be done before balance is deleted
        user_id = request.user.id
        if enrol_fields:
            check_join_with_pay(enrol_fields, user_id)

        entry.scheme_account.delete_saved_balance()
        entry.scheme_account.delete_cached_balance()

        if enrol_fields:
            self._replace_with_enrol_fields(
                request, entry, entry.scheme_account, enrol_fields, scheme, payment_cards_to_link
            )
            metrics_route = MembershipCardAddRoute.ENROL
        else:
            metrics_route, account = self._handle_replace_add_and_auth_fields(
                entry,
                add_fields,
                auth_fields,
                payment_cards_to_link,
                user_id,
            )

        if metrics_route:
            membership_card_update_counter.labels(
                channel=request.channels_permit.bundle_id,
                scheme=scheme.slug,
                route=metrics_route.value,
            ).inc()

        entry.save()
        # auth_provided_mapping =
        # MembershipCardSerializer.get_mcard_user_auth_provided_map(request, entry.scheme_account)
        return Response(
            self.get_serializer_by_request(
                entry.scheme_account,
                context={
                    # "mcard_user_auth_provided_map": auth_provided_mapping,
                    "user_id": self.request.user.id
                },
            ).data,
            status=status.HTTP_200_OK,
        )

    @staticmethod
    def _replace_with_enrol_fields(
        req: "Request",
        scheme_acc_entry: SchemeAccountEntry,
        account: SchemeAccount,
        enrol_fields: dict,
        scheme: Scheme,
        payment_cards_to_link: list,
    ) -> None:
        enrol_fields = detect_and_handle_escaped_unicode(enrol_fields)
        validated_data, serializer, _ = SchemeAccountJoinMixin.validate(
            data=enrol_fields,
            scheme_account=account,
            user=req.user,
            permit=req.channels_permit,
            join_scheme=account.scheme,
        )

        # Some schemes will provide a main answer during enrol, which should be saved
        # e.g harvey nichols email
        required_questions = {question["type"] for question in scheme.get_required_questions}
        answer_types = set(validated_data).intersection(required_questions)
        account.alt_main_answer = ""
        if answer_types:
            if len(answer_types) > 1:
                raise ParseError("Only one type of main answer should be provided")
            account.alt_main_answer = validated_data[answer_types.pop()]

        scheme_acc_entry.set_link_status(AccountLinkStatus.JOIN_ASYNC_IN_PROGRESS)

        scheme_acc_entry.schemeaccountcredentialanswer_set.all().delete()
        account.save(update_fields=["alt_main_answer"])
        async_join.delay(
            scheme_account_id=account.id,
            user_id=req.user.id,
            serializer=serializer,
            scheme_id=scheme.id,
            validated_data=validated_data,
            channel=req.channels_permit.bundle_id,
            payment_cards_to_link=payment_cards_to_link,
            history_kwargs={
                "user_info": user_info(user_id=req.channels_permit.user.id, channel=req.channels_permit.bundle_id),
                "journey": "enrol",
            },
        )

    def _handle_replace_add_and_auth_fields(
        self,
        scheme_acc_entry: SchemeAccountEntry,
        add_fields: dict,
        auth_fields: dict,
        payment_cards_to_link: list,
        user_id: int,
    ) -> tuple[MembershipCardAddRoute, SchemeAccount]:
        if auth_fields:
            auth_fields = detect_and_handle_escaped_unicode(auth_fields)

        account = scheme_acc_entry.scheme_account

        new_answers, main_answer_type, main_answer_value = self._get_new_answers(add_fields, auth_fields)
        main_answer_field = account.get_key_cred_field_from_question_type(main_answer_type)

        metrics_route = MembershipCardAddRoute.UPDATE

        # update credentials
        UpdateCredentialsMixin().update_credentials(
            scheme_account=account,
            data=new_answers,
            questions=account.scheme.questions.all(),
            scheme_account_entry=scheme_acc_entry,
        )

        relink_pll = False

        # If main answer is different from current, then we need to link to other account/create a new one.
        if main_answer_value != getattr(scheme_acc_entry.scheme_account, main_answer_field):
            account = self._create_and_link_to_new_account_from_main_answer(
                scheme_account_entry=scheme_acc_entry,
                main_answer_field=main_answer_field,
                main_answer_value=main_answer_value,
            )

            relink_pll = True

        scheme_acc_entry.set_link_status(AccountLinkStatus.PENDING)

        # todo: we should be able to replace this with async_balance but will need to consider event handling.
        async_balance_with_updated_credentials.delay(
            instance_id=account.id,
            scheme_account_entry=scheme_acc_entry,
            payment_cards_to_link=payment_cards_to_link,
            relink_pll=relink_pll,
        )

        return metrics_route, account

    @censor_and_decorate
    def destroy(self, request, *args, **kwargs):
        entry = get_object_or_404(self.get_queryset(), scheme_account=self.kwargs["pk"])
        if entry.link_status in (AccountLinkStatus.join_pending() + AccountLinkStatus.register_pending()):
            # Ideally we would create a different error message for pending registrations as this is a little misleading
            # , but this would mean non-agreed changes to the API for Barclays so will keep this the same for now.
            error = {"join_pending": "Membership card cannot be deleted until the Join process has completed."}
            return Response(error, status=status.HTTP_405_METHOD_NOT_ALLOWED)

        deleted_membership_card_cleanup.delay(
            entry,
            arrow.utcnow().format(),
            channel_slug=request.channels_permit.bundle_id,
            history_kwargs={
                "user_info": user_info(
                    user_id=request.channels_permit.user.id, channel=request.channels_permit.bundle_id
                )
            },
        )
        return Response({}, status=status.HTTP_200_OK)

    @censor_and_decorate
    def membership_plan(self, request, mcard_id):
        mcard = get_object_or_404(SchemeAccount, id=mcard_id)
        context = self.get_serializer_context()
        self.response_serializer = SelectSerializer.MEMBERSHIP_PLAN
        return Response(self.get_serializer_by_request(mcard.scheme, context=context).data)

    def _collect_field_content(self, fields_type, data, label_to_type):
        try:
            fields = data["account"].get(fields_type, [])
            api_version = get_api_version(self.request)
            field_content = {}
            encrypted_fields = {}

            for item in fields:
                field_type = label_to_type[fields_type][item["column"]]
                self._filter_sensitive_fields(field_content, encrypted_fields, field_type, item, api_version)

            if encrypted_fields:
                field_content.update(
                    self._decrypt_sensitive_fields(self.request.channels_permit.bundle_id, encrypted_fields)
                )

            if EMAIL in field_content:
                field_content[EMAIL] = field_content[EMAIL].lower()

        except (TypeError, KeyError, ValueError) as e:
            logger.debug(f"Error collecting field content - {type(e)} {e.args[0]}")
            raise ParseError from None

        return field_content

    @staticmethod
    def _decrypt_sensitive_fields(bundle_id: str, fields: dict) -> dict:
        if needs_decryption(fields.values()):
            rsa_key_pem = get_bundle_key(bundle_id=bundle_id, key_type=KeyType.PRIVATE_KEY)
            try:
                with sentry_sdk.start_span(op="decryption", description="membership card"):
                    decrypted_values = zip(
                        fields.keys(), rsa_decrypt_base64(rsa_key_pem, list(fields.values())), strict=False
                    )
            except ValueError as e:
                raise ValueError("Failed to decrypt sensitive fields") from e

            fields.update(decrypted_values)

        return fields

    @staticmethod
    def _filter_sensitive_fields(
        field_content: dict, encrypted_fields: dict, field_type: dict, item: dict, api_version: Version
    ) -> None:
        credential_type = field_type["type"]
        answer_type = field_type["answer_type"]

        if api_version >= Version.v1_2 and answer_type == AnswerTypeChoices.SENSITIVE.value:
            encrypted_fields[credential_type] = item["value"]
        else:
            field_content[credential_type] = item["value"]

    def _collect_updated_answers(self, scheme: Scheme, scheme_questions: list) -> tuple[dict | None, dict | None]:
        data = self.request.data
        label_to_type = scheme.get_question_type_dict(scheme_questions)
        out_fields = {}
        for fields_type in self.create_update_fields:
            out_fields[fields_type] = self._extract_consent_data(scheme, fields_type, data)
            out_fields[fields_type].update(self._collect_field_content(fields_type, data, label_to_type))

        if not out_fields or out_fields["enrol_fields"]:
            raise ParseError

        if out_fields["registration_fields"]:
            return None, out_fields["registration_fields"]

        return {**out_fields["add_fields"], **out_fields["authorise_fields"]}, None

    def _collect_fields_and_determine_route(self) -> tuple[Scheme, dict, dict, dict]:
        try:
            if not self.request.channels_permit.is_scheme_available(int(self.request.data["membership_plan"])):
                raise ParseError("membership plan not allowed for this user.")

            scheme = Scheme.get_scheme_and_questions_by_scheme_id(self.request.data["membership_plan"])

            if not self.request.channels_permit.permit_test_access(scheme):
                raise ParseError("membership plan not allowed for this user.")

        except KeyError:
            raise ParseError("required field membership_plan is missing") from None
        except (ValueError, Scheme.DoesNotExist):
            raise ParseError from None

        add_fields, auth_fields, enrol_fields = self._collect_credentials_answers(self.request.data, scheme=scheme)
        return scheme, auth_fields, enrol_fields, add_fields

    def _handle_create_link_route(
        self, user: CustomUser, scheme: Scheme, auth_fields: dict, add_fields: dict, payment_cards_to_link: list
    ) -> tuple[SchemeAccount, SchemeAccountEntry, int, MembershipCardAddRoute]:
        HISTORY_CONTEXT.journey = journey = SchemeAccountJourney.ADD.value

        serializer = self.get_serializer(data={"scheme": scheme.id, "order": 0, **add_fields})
        serializer.is_valid(raise_exception=True)

        # Create or retrieve scheme_account
        (
            scheme_account,
            _,
            account_created,
            answer_type,
            main_answer,
            sch_acc_entry,
            sch_acc_entry_created,
        ) = self.create_account_with_valid_data(serializer, user, scheme)

        if sch_acc_entry_created:
            self.create_main_answer_credential(
                answer_type=answer_type, scheme_account_entry=sch_acc_entry, main_answer=main_answer
            )

        return_status = status.HTTP_201_CREATED if account_created else status.HTTP_200_OK

        if account_created and (auth_fields or not scheme.authorisation_required):
            # scheme account created & auth fields provided or the scheme does not require authorisation

            history_kwargs = {
                "user_info": user_info(
                    user_id=self.request.channels_permit.user.id, channel=self.request.channels_permit.bundle_id
                ),
                "journey": journey,
            }

            if scheme.tier in Scheme.TRANSACTION_MATCHING_TIERS:
                metrics_route = MembershipCardAddRoute.LINK
            else:
                metrics_route = MembershipCardAddRoute.WALLET_ONLY

            sch_acc_entry.link_status = AccountLinkStatus.ADD_AUTH_PENDING
            sch_acc_entry.save(update_fields=["link_status"])
            logger.debug(
                f"scheme_account_id: {scheme_account.id}, "
                f"scheme_id: {scheme.id} "
                f"- Setting link_status as ADD_AUTH_PENDING"
            )
            # send add_and_auth event to data_warehouse
            addauth_request_lc_event(user, scheme_account, self.request.channels_permit.bundle_id)
            async_link.delay(auth_fields, scheme_account.id, user.id, payment_cards_to_link, history_kwargs)

        elif not auth_fields and scheme.authorisation_required:
            # no auth provided, new scheme account created
            metrics_route = MembershipCardAddRoute.WALLET_ONLY
            self._handle_wallet_only_link(sch_acc_entry, sch_acc_entry_created)
        else:
            # auth fields provided, new scheme account not created (linking to existing scheme account)
            if not sch_acc_entry_created:
                auth_request_lc_event(user, scheme_account, self.request.channels_permit.bundle_id)
                sch_acc_entry.set_link_status(AccountLinkStatus.AUTH_PENDING)
            else:
                addauth_request_lc_event(user, scheme_account, self.request.channels_permit.bundle_id)
                sch_acc_entry.set_link_status(AccountLinkStatus.ADD_AUTH_PENDING)

            metrics_route = MembershipCardAddRoute.MULTI_WALLET
            async_link.delay(
                auth_fields,
                scheme_account.id,
                user.id,
                payment_cards_to_link,
                history_kwargs={
                    "user_info": user_info(user_id=user.id, channel=self.request.channels_permit.bundle_id)
                },
            )

        return scheme_account, sch_acc_entry, return_status, metrics_route

    @staticmethod
    def _handle_create_join_route(
        user: CustomUser, channels_permit: Permit, scheme: Scheme, enrol_fields: dict, payment_cards_to_link: list
    ) -> tuple[SchemeAccount, SchemeAccountEntry, int]:
        history_journey = SchemeAccountJourney.ENROL.value
        HISTORY_CONTEXT.journey = history_journey

        check_join_with_pay(enrol_fields, user.id)
        # Some schemes will provide a main answer during enrol, which should be saved
        # e.g harvey nichols email
        required_questions = {
            question.type
            for question in scheme.questions.all()
            if any((question.manual_question, question.scan_question, question.one_question_link))
        }
        answer_types = set(enrol_fields).intersection(required_questions)
        main_answer_field = ""
        main_answer = ""
        if answer_types:
            if len(answer_types) > 1:
                raise ParseError("Only one type of main answer should be provided")
            answer_type = answer_types.pop()
            main_answer = enrol_fields[answer_type]
            main_answer_field = SchemeAccount.get_key_cred_field_from_question_type(answer_type)

        # PLR logic will be revisited before going live in other applications
        plr_slugs = [
            "fatface",
            "burger-king-rewards",
            "whsmith-rewards",
        ]
        if scheme.slug in plr_slugs:
            # at the moment, all PLR schemes provide email as an enrol field.
            # if this changes, we'll need to rework this code.
            email = enrol_fields["email"]

            # todo: this needs rework with the new credentials changes
            other_scheme_links = SchemeAccountEntry.objects.filter(
                scheme_account__scheme_id=scheme.id,
                schemeaccountcredentialanswer__answer=email,
            )

            if other_scheme_links.exists():
                scheme_account = other_scheme_links.first().scheme_account
                sch_acc_entry, _ = SchemeAccountEntry.create_or_retrieve_link(user=user, scheme_account=scheme_account)
                return scheme_account, sch_acc_entry, status.HTTP_201_CREATED

        creation_args = {
            "order": 0,
            "scheme_id": scheme.id,
            "originating_journey": JourneyTypes.JOIN,
        }

        if main_answer_field:
            creation_args[main_answer_field] = main_answer

        scheme_account = SchemeAccount(**creation_args)

        validated_data, serializer, _ = SchemeAccountJoinMixin.validate(
            data=enrol_fields,
            scheme_account=scheme_account,
            user=user,
            permit=channels_permit,
            join_scheme=scheme,
        )

        scheme_account.save()
        sch_acc_entry = SchemeAccountEntry.objects.create(
            user=user,
            scheme_account=scheme_account,
            link_status=AccountLinkStatus.JOIN_ASYNC_IN_PROGRESS,
        )

        # send this event to data_warehouse
        join_request_lc_event(sch_acc_entry, channels_permit.bundle_id)

        async_join.delay(
            scheme_account.id,
            user.id,
            serializer,
            scheme.id,
            validated_data,
            channels_permit.bundle_id,
            payment_cards_to_link,
            history_kwargs={
                "user_info": user_info(user_id=channels_permit.user.id, channel=channels_permit.bundle_id),
                "journey": history_journey,
            },
        )
        return scheme_account, sch_acc_entry, status.HTTP_201_CREATED

    @staticmethod
    def _get_manual_question(scheme_slug, scheme_questions):
        for question in scheme_questions:
            if question.manual_question:
                return question.type

        raise SchemeCredentialQuestion.DoesNotExist(f"could not find the manual question for scheme: {scheme_slug}.")

    @staticmethod
    def _match_scheme_question_fields(field_name, data, questions):
        """
        Method is to check what's being passed in matches the SchemeCredentialQuestion model.
        Raises a ValidationError is a mismatch is found.
        example:
        add_fields - {'column': 'card_number', 'value': 'xxxxxx'}
        model - card_number - add_field: False, auth_field: True
        """
        field_name_mapping = {
            "add_fields": "add_field",
            "authorise_fields": "auth_field",
            "registration_fields": "register_field",
            "enrol_fields": "enrol_field",
        }

        fields = data["account"].get(field_name, [])
        lables = [x["label"] for x in questions]

        valid_columns = []

        # Get a list of questions that matches the field_name and is True
        for question in questions:
            if question[field_name_mapping[field_name]]:
                valid_columns.append(question["label"])

        for field in fields:
            # Exclude anything that's not part of the scheme credential questions.
            if field["column"] not in lables:
                continue
            if field["column"] not in valid_columns:
                raise ValidationError("Column does not match field type.")

    def _collect_credentials_answers(self, data: dict, scheme: Scheme) -> tuple[dict | None, dict | None, dict | None]:
        try:
            scheme_questions = scheme.questions.all()
            question_types = scheme_questions.values(
                "label", "add_field", "auth_field", "register_field", "enrol_field"
            )
            label_to_type = scheme.get_question_type_dict(scheme_questions)
            fields = {}

            for field_name in self.create_update_fields:
                # Checks what being passed in matched the scheme question
                # create, update fields (add, auth, register, enrol)
                self._match_scheme_question_fields(field_name, data, question_types)
                fields[field_name] = self._extract_consent_data(scheme, field_name, data)
                fields[field_name].update(self._collect_field_content(field_name, data, label_to_type))

        except (KeyError, ValueError) as e:
            logger.exception(e)
            raise ParseError() from None

        if fields["enrol_fields"]:
            return None, None, fields["enrol_fields"]

        if not fields["add_fields"] and scheme.authorisation_required:
            manual_question = self._get_manual_question(scheme.slug, scheme_questions)

            try:
                fields["add_fields"].update({manual_question: fields["authorise_fields"].pop(manual_question)})
            except KeyError:
                raise ParseError() from None

        elif not fields["add_fields"]:
            raise ParseError("missing fields")

        return fields["add_fields"], fields["authorise_fields"], None

    def _extract_consent_data(self, scheme: Scheme, field: str, data: dict) -> dict:
        data_provided = data["account"].get(field)

        if not data_provided:
            return {}

        if not hasattr(self, "consent_links") or not self.consent_links:
            client_app = self.request.channels_permit.client
            self.consent_links = ThirdPartyConsentLink.get_by_scheme_and_client(scheme=scheme, client_app=client_app)

        provided_consent_keys = self.match_consents(self.consent_links, data_provided)
        if not provided_consent_keys:
            return {"consents": []}

        consents = self._build_consents(data_provided, provided_consent_keys)

        # remove consents information from provided credentials data
        data["account"][field] = [item for item in data_provided if item["column"] not in provided_consent_keys]

        return {"consents": consents}

    def _build_consents(self, data_provided, provided_consent_keys):
        provided_consent_data = {
            item["column"]: item for item in data_provided if item["column"] in provided_consent_keys
        }

        return [
            {"id": link.consent_id, "value": provided_consent_data[link.consent_label]["value"]}
            for link in self.consent_links
            if provided_consent_data.get(link.consent_label)
        ]

    @staticmethod
    def _handle_wallet_only_link(
        scheme_account_entry: "SchemeAccountEntry",
        sch_acc_entry_created: bool,
    ):
        """Handles scheme accounts for when only add fields are provided."""
        if sch_acc_entry_created:
            scheme_account_entry.link_status = AccountLinkStatus.WALLET_ONLY

            scheme_account_entry.save(update_fields=["link_status"])
            logger.info(
                f"Set SchemeAccount (id={scheme_account_entry.scheme_account_id}) for "
                f"User (id={scheme_account_entry.user_id}) to Wallet Only status"
            )
        else:
            raise AlreadyExistsError

    @staticmethod
    def match_consents(consent_links, data_provided):
        consent_labels = {link.consent_label for link in consent_links}
        data_keys = {data["column"] for data in data_provided}

        return data_keys.intersection(consent_labels)

    @staticmethod
    def allowed_answers(scheme: Scheme) -> list[str]:
        allowed_types = []
        if scheme.manual_question:
            allowed_types.append(scheme.manual_question.type)
        if scheme.scan_question:
            allowed_types.append(scheme.scan_question.type)
        if scheme.one_question_link:
            allowed_types.append(scheme.one_question_link.type)
        return allowed_types


class ListMembershipCardView(MembershipCardView):
    current_scheme = None
    scheme_questions = None
    authentication_classes = (PropertyAuthentication,)
    response_serializer = SelectSerializer.MEMBERSHIP_CARD
    override_serializer_classes = {"GET": MembershipCardSerializer, "POST": LinkMembershipCardSerializer}

    @censor_and_decorate
    def list(self, request, *args, **kwargs):
        entries = self.filter_queryset(self.get_queryset()).exclude(link_status=AccountLinkStatus.JOIN)

        accounts = [sae.scheme_account for sae in entries.all()]

        # auth_provided_mapping = MembershipCardSerializer.get_mcard_user_auth_provided_map(request, accounts)
        response = self.get_serializer_by_request(
            accounts,
            many=True,
            context={
                # "mcard_user_auth_provided_map": auth_provided_mapping,
                "user_id": self.request.user.id
            },
        ).data

        return Response(response, status=200)

    @censor_and_decorate
    def create(self, request, *args, **kwargs):
        scheme, auth_fields, enrol_fields, add_fields = self._collect_fields_and_determine_route()
        self.current_scheme = scheme
        self.scheme_questions = scheme.questions.all()

        if auto_link(request):
            payment_cards_to_link = PaymentCardAccountEntry.objects.filter(user_id=request.user.id).values_list(
                "payment_card_account_id", flat=True
            )
        else:
            payment_cards_to_link = []

        if enrol_fields:
            enrol_fields = detect_and_handle_escaped_unicode(enrol_fields)
            metrics_route = MembershipCardAddRoute.ENROL
            account, sch_acc_entry, status_code = self._handle_create_join_route(
                request.user, request.channels_permit, scheme, enrol_fields, payment_cards_to_link
            )
        else:
            link_consents = add_fields.get("consents", []) + auth_fields.get("consents", [])
            if add_fields:
                add_fields["consents"] = link_consents
            if auth_fields:
                auth_fields = detect_and_handle_escaped_unicode(auth_fields)
                auth_fields["consents"] = link_consents

            account, sch_acc_entry, status_code, metrics_route = self._handle_create_link_route(
                request.user, scheme, auth_fields, add_fields, payment_cards_to_link
            )

            # Update originating journey type
            account.set_add_originating_journey()

        if scheme.slug in settings.SCHEMES_COLLECTING_METRICS:
            send_merchant_metrics_for_new_account.delay(request.user.id, account.id, account.scheme.slug)

        if metrics_route:
            membership_card_add_counter.labels(
                channel=request.channels_permit.bundle_id, scheme=scheme.slug, route=metrics_route.value
            ).inc()

        return Response(
            self.get_serializer_by_request(
                account,
                context={
                    "request": request,
                    "user_id": self.request.user.id,
                },
            ).data,
            status=status_code,
        )


class PortalUsersLookupView(GenericViewSet):
    """
    GET `/ubiquity/users/lookup?s=...`

    Expected response payload:

    ```json
    [
        {
            "user_id": 1,
            "is_active": false,
            "channel": "com.stuff.1",
            "membership_cards": [
                ...,  # GET /membership_cards payload without removing empty values
            ],
        },
        {
            "user_id": 2,
            "is_active": true,
            "channel": "com.stuff.2",
            "membership_cards": [
                ...,  # GET /membership_cards payload without removing empty values
            ],
        },
    ]
    ```
    """

    authentication_classes = (InternalServiceAuthentication,)

    def get_queryset(self, lookup_val: str):
        return (
            CustomUser.all_objects.prefetch_related("scheme_account_set__scheme")
            .filter(Q(email=lookup_val) | Q(external_id=lookup_val))
            .all()
        )

    def list(self, request: HttpRequest, *args: t.Any, **kwargs: t.Any) -> Response:
        if not (lookup_val := request.GET.get("s")):
            raise ValidationError("Lookup value not provided. Expected non empty query param 's'.")

        return Response(
            [
                {
                    "user_id": user.id,
                    "is_active": user.is_active,
                    "channel": user.bundle_id,
                    "membership_cards": MembershipCardSerializer(
                        user.scheme_account_set, context={"user_id": user.id}, many=True
                    ).data,
                }
                for user in self.get_queryset(lookup_val)
            ],
            status=200,
        )


class CardLinkView(VersionedSerializerMixin, ModelViewSet):
    authentication_classes = (PropertyAuthentication,)

    # @todo PLL stuff
    def update_payment(self, request, *args, **kwargs):
        self.response_serializer = SelectSerializer.PAYMENT_CARD
        link, status_code = self._update_link(request.user, kwargs["pcard_id"], kwargs["mcard_id"])
        link.payment_card_account.refresh_from_db(fields=["pll_links"])
        serializer = self.get_serializer_by_request(link.payment_card_account)
        return Response(serializer.data, status_code)

    # @todo PLL stuff
    @censor_and_decorate
    def update_membership(self, request, *args, **kwargs):
        self.response_serializer = SelectSerializer.MEMBERSHIP_CARD
        link, status_code = self._update_link(request.user, kwargs["pcard_id"], kwargs["mcard_id"])
        link.scheme_account.refresh_from_db(fields=["pll_links"])

        # auth_provided_mapping =
        # MembershipCardSerializer.get_mcard_user_auth_provided_map(request, link.scheme_account)
        serializer = self.get_serializer_by_request(
            link.scheme_account,
            context={
                # "mcard_user_auth_provided_map": auth_provided_mapping,
                "user_id": request.user.id
            },
        )

        return Response(serializer.data, status_code)

    @censor_and_decorate
    def destroy_payment(self, request, *args, **kwargs):
        pcard, _, error = self._destroy_link(request.user, kwargs["pcard_id"], kwargs["mcard_id"])
        if error:
            return HttpResponseForbidden(
                "Unable to remove link. Payment and Loyalty card combination exists in other wallets"
            )

        return Response({}, status.HTTP_200_OK)

    @censor_and_decorate
    def destroy_membership(self, request, *args, **kwargs):
        _, mcard, error = self._destroy_link(request.user, kwargs["pcard_id"], kwargs["mcard_id"])
        if error:
            return HttpResponseForbidden(
                "Unable to remove link. Payment and Loyalty card combination exists in other wallets"
            )

        return Response({}, status.HTTP_200_OK)

    def _destroy_link(
        self, user: CustomUser, pcard_id: int, mcard_id: int
    ) -> tuple[PaymentCardAccount, SchemeAccount, bool]:
        error = False
        pcard, mcard = self._collect_cards(pcard_id, mcard_id, user)

        try:
            link = PaymentCardSchemeEntry.objects.get(scheme_account=mcard, payment_card_account=pcard)
        except PaymentCardSchemeEntry.DoesNotExist:
            raise NotFound("The link that you are trying to delete does not exist.") from None

        # Check if link is in multiple wallets
        if link.payment_card_account.user_set.count() > 1:
            error = True
            return pcard, mcard, error

        # Check that if the Payment card has visa slug (VOP) and that the card is not linked to same merchant
        # in list with activated status - if so call deactivate and then delete link
        activations = VopActivation.find_activations_matching_links([link])
        link.delete()
        PaymentCardSchemeEntry.deactivate_activations(activations)
        return pcard, mcard, error

    # @todo PLL stuff - this looks wrong!
    def _update_link(self, user: CustomUser, pcard_id: int, mcard_id: int) -> tuple[PaymentCardSchemeEntry, int]:
        pcard, mcard = self._collect_cards(pcard_id, mcard_id, user)
        status_code = status.HTTP_200_OK

        try:
            # todo: PLL stuff
            existing_link = PaymentCardSchemeEntry.objects.get(
                payment_card_account=pcard, scheme_account__scheme_id=mcard.scheme_id
            )
            if existing_link.scheme_account_id != mcard.id:
                raise PaymentCardSchemeEntry.MultipleObjectsReturned
            else:
                link = existing_link

        except PaymentCardSchemeEntry.MultipleObjectsReturned:
            raise ValidationError(
                {
                    "PLAN_ALREADY_LINKED": (
                        f"Payment card {pcard.id} is already linked to a membership card "
                        f"that belongs to the membership plan {mcard.scheme_id}"
                    )
                }
            ) from None
        except PaymentCardSchemeEntry.DoesNotExist:
            # todo: PLL stuff
            # link = PaymentCardSchemeEntry(
            #    scheme_account=mcard, payment_card_account=pcard
            # ).get_instance_with_active_status()

            user_pll_assoc = PllUserAssociation.link_users_scheme_account_to_payment(mcard, pcard, user)
            link = user_pll_assoc.pll
            # link.save()  - done in above call
            # link.vop_activate_check()
            status_code = status.HTTP_201_CREATED
            audit.write_to_db(link)

        return link, status_code

    @staticmethod
    def _collect_cards(
        payment_card_id: int, membership_card_id: int, user: CustomUser
    ) -> tuple[PaymentCardAccount, SchemeAccount]:
        try:
            filters = {"is_deleted": False}
            payment_card = user.payment_card_account_set.get(pk=payment_card_id, **filters)
            membership_card = user.scheme_account_set.get(
                pk=membership_card_id, schemeaccountentry__link_status=AccountLinkStatus.ACTIVE, **filters
            )

        except PaymentCardAccount.DoesNotExist:
            raise NotFound(f"The payment card of id {payment_card_id} was not found.") from None
        except SchemeAccount.DoesNotExist:
            raise NotFound(
                f"The membership card of id {membership_card_id} was not found or it is a Store type card that "
                f"cannot be linked."
            ) from None
        except KeyError:
            raise ParseError from None

        return payment_card, membership_card


class MembershipPlanView(VersionedSerializerMixin, ModelViewSet):
    authentication_classes = (PropertyAuthentication,)
    serializer_class = MembershipPlanSerializer
    response_serializer = SelectSerializer.MEMBERSHIP_PLAN

    def get_queryset(self):
        return self.request.channels_permit.scheme_query(Scheme.objects)

    @CacheApiRequest(settings.REDIS_MPLANS_CACHE_PREFIX, settings.REDIS_MPLANS_CACHE_EXPIRY, membership_plan_key)
    @censor_and_decorate
    def retrieve(self, request, *args, **kwargs):
        self.serializer_class = self.get_serializer_class_by_request()
        return super().retrieve(request, *args, **kwargs)


class ListMembershipPlanView(VersionedSerializerMixin, ModelViewSet, IdentifyCardMixin):
    authentication_classes = (PropertyAuthentication,)
    serializer_class = MembershipPlanSerializer
    response_serializer = SelectSerializer.MEMBERSHIP_PLAN

    def get_queryset(self):
        return self.request.channels_permit.scheme_query(Scheme.objects)

    @CacheApiRequest(settings.REDIS_MPLANS_CACHE_PREFIX, settings.REDIS_MPLANS_CACHE_EXPIRY, membership_plan_key)
    @censor_and_decorate
    def list(self, request, *args, **kwargs):
        self.serializer_class = self.get_serializer_class_by_request()
        return super().list(request, *args, **kwargs)

    @censor_and_decorate
    def identify(self, request):
        try:
            base64_image = request.data["card"]["base64_image"]
        except KeyError:
            raise ParseError from None

        json = self._get_scheme(base64_image)
        if json["status"] != "success" or json["reason"] == "no match":
            return Response({"status": "failure", "message": json["reason"]}, status=400)

        scheme = get_object_or_404(Scheme, id=json["scheme_id"])
        return Response(self.get_serializer_by_request(scheme).data)


class MembershipTransactionView(ModelViewSet, VersionedSerializerMixin, MembershipTransactionsMixin):
    authentication_classes = (PropertyAuthentication,)
    serializer_class = TransactionSerializer
    response_serializer = SelectSerializer.MEMBERSHIP_TRANSACTION

    @censor_and_decorate
    def retrieve(self, request, *args, **kwargs):
        url = "{}/transactions/{}".format(settings.HADES_URL, kwargs["transaction_id"])
        headers = {"Authorization": self._get_auth_token(request.user.id), "Content-Type": "application/json"}
        resp = self.hades_request(url, headers=headers)
        resp_json = resp.json()
        if resp.status_code == 200 and resp_json:
            if isinstance(resp_json, list) and len(resp_json) > 1:
                logger.warning("Hades responded with more than one transaction for a single id")
            transaction = resp_json[0]
            serializer = self.serializer_class(data=transaction)
            serializer.is_valid(raise_exception=True)

            if self._account_belongs_to_user(request, serializer.initial_data.get("scheme_account_id")):
                return Response(self.get_serializer_by_request(serializer.validated_data).data)

        return Response({})

    @censor_and_decorate
    def list(self, request, *args, **kwargs):
        url = f"{settings.HADES_URL}/transactions/user/{request.user.id}"
        headers = {"Authorization": self._get_auth_token(request.user.id), "Content-Type": "application/json"}
        resp = self.hades_request(url, headers=headers)
        resp_json = resp.json()
        if resp.status_code == 200 and resp_json:
            context = {"user": request.user, "bundle": request.channels_permit.bundle}
            serializer = self.serializer_class(data=resp_json, many=True, context=context)
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data[:5]  # limit to 5 transactions as per documentation
            if data:
                return Response(self.get_serializer_by_request(data, many=True).data)

        return Response([])

    @censor_and_decorate
    def composite(self, request, *args, **kwargs):
        transactions = []
        scheme_account_entry = request.channels_permit.scheme_account_entry_query(
            SchemeAccountEntry.objects.filter(scheme_account_id=kwargs["mcard_id"]).select_related("scheme_account"),
            user_id=request.user.id,
            user_filter=True,
        ).first()
        if scheme_account_entry and scheme_account_entry.display_status == AccountLinkStatus.ACTIVE:
            transactions = scheme_account_entry.scheme_account.transactions

        return Response(transactions)

    @staticmethod
    def _account_belongs_to_user(request: "Request", mcard_id: int) -> bool:
        return request.channels_permit.scheme_account_query(
            SchemeAccount.objects.filter(id=mcard_id), user_id=request.user.id, user_filter=True
        ).exists()
