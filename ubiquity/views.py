import logging
import re
import typing as t

import arrow
from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Count, Q, QuerySet
from rest_framework import status
from rest_framework.exceptions import APIException, NotFound, ParseError, ValidationError
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_201_CREATED
from rest_framework.viewsets import ModelViewSet
from rustyjeff import rsa_decrypt_base64
from shared_config_storage.credentials.encryption import BLAKE2sHash
from shared_config_storage.credentials.utils import AnswerTypeChoices

from hermes.channels import Permit
from hermes.settings import Version
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
from scheme.credentials import CASE_SENSITIVE_CREDENTIALS, DATE_TYPE_CREDENTIALS, PAYMENT_CARD_HASH, POSTCODE
from scheme.mixins import (
    BaseLinkMixin,
    IdentifyCardMixin,
    SchemeAccountCreationMixin,
    SchemeAccountJoinMixin,
    UpdateCredentialsMixin,
)
from scheme.models import Scheme, SchemeAccount, SchemeCredentialQuestion, ThirdPartyConsentLink
from scheme.views import RetrieveDeleteAccount
from ubiquity.authentication import PropertyAuthentication, PropertyOrServiceAuthentication
from ubiquity.cache_decorators import CacheApiRequest, membership_plan_key
from ubiquity.censor_empty_fields import censor_and_decorate
from ubiquity.channel_vault import KeyType, SecretKeyName, get_key, get_secret_key
from ubiquity.influx_audit import audit
from ubiquity.models import (
    PaymentCardAccountEntry,
    PaymentCardSchemeEntry,
    SchemeAccountEntry,
    ServiceConsent,
    VopActivation,
)
from ubiquity.tasks import (
    async_all_balance,
    async_balance,
    async_join,
    async_link,
    async_registration,
    auto_link_membership_to_payments,
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
    ServiceConsentSerializer,
    TransactionSerializer,
)
from user.models import CustomUser
from user.serializers import UbiquityRegisterSerializer

if t.TYPE_CHECKING:
    from rest_framework.request import Request
    from rest_framework.serializers import Serializer

escaped_unicode_pattern = re.compile(r"\\(\\u[a-fA-F0-9]{4})")
logger = logging.getLogger(__name__)


class ConflictError(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Attempting to create two or more identical users at the same time."
    default_code = "conflict"


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

        # Ensure that we only consider membership cards in a user's wallet which can be PLL linked
        wallet_scheme_accounts = SchemeAccount.objects.filter(
            user_set=user, scheme__tier=Scheme.PLL, schemeaccountentry__auth_status=SchemeAccountEntry.AUTHORISED
        ).all()

        if wallet_scheme_accounts:
            if payment_card_account.status == PaymentCardAccount.ACTIVE:
                auto_link_payment_to_memberships(wallet_scheme_accounts, payment_card_account, just_created)
            else:
                auto_link_payment_to_memberships.delay(
                    [sa.id for sa in wallet_scheme_accounts],
                    payment_card_account.id,
                    just_created,
                    history_kwargs={"user_info": user_info(user_id=user.id, channel=bundle_id)}
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
    ) -> t.Tuple[t.Optional[PaymentCardAccount], PaymentCardRoutes, int]:
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
        elif card.expiry_month == data["expiry_month"] and card.expiry_year == data["expiry_year"]:
            route = PaymentCardRoutes.EXISTS_IN_OTHER_WALLET
        else:
            route = PaymentCardRoutes.NEW_CARD

        return card, route, status_code

    @staticmethod
    def _add_hash(new_hash: str, card: PaymentCardAccount) -> None:
        if new_hash and not card.hash:
            card.hash = new_hash
            card.save(update_fields=["hash"])

    @staticmethod
    def _link_account_to_new_user(account: PaymentCardAccount, user: CustomUser) -> None:
        try:
            with transaction.atomic():
                PaymentCardAccountEntry.objects.create(user=user, payment_card_account=account)
        except IntegrityError:
            pass

    @staticmethod
    def _collect_creation_data(
            request_data: dict, allowed_issuers: t.List[int], version: "Version", bundle_id: str = None
    ) -> t.Tuple[dict, dict]:
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
            logger.debug(f"error creating payment card: {repr(e)}")
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
    serializer_class = ServiceConsentSerializer
    response_serializer = SelectSerializer.SERVICE

    @censor_and_decorate
    def retrieve(self, request, *args, **kwargs):
        async_all_balance.delay(request.user.id, self.request.channels_permit)
        return Response(self.get_serializer_by_request(request.user.serviceconsent).data)

    @censor_and_decorate
    def create(self, request, *args, **kwargs):
        status_code = HTTP_200_OK
        consent_data = request.data["consent"]
        if "email" not in consent_data:
            raise ParseError

        try:
            if request.channels_permit.auth_by == "bink":
                user = request.channels_permit.user
            else:
                user = CustomUser.objects.get(client=request.channels_permit.client, external_id=request.prop_id)
        except CustomUser.DoesNotExist:
            new_user_data = {
                "client_id": request.channels_permit.client.pk,
                "bundle_id": request.channels_permit.bundle_id,
                "email": consent_data["email"],
                "external_id": request.prop_id,
            }
            status_code = HTTP_201_CREATED
            new_user = UbiquityRegisterSerializer(data=new_user_data, context={"bearer_registration": True})
            new_user.is_valid(raise_exception=True)

            try:
                user = new_user.save()
            except IntegrityError:
                raise ConflictError

            consent = self._add_consent(user, consent_data, service=True)
            service_creation_counter.labels(channel=request.channels_permit.bundle_id).inc()
        else:
            if not hasattr(user, "serviceconsent"):
                status_code = HTTP_201_CREATED
                consent = self._add_consent(user, consent_data)

            else:
                consent = self.get_serializer_by_request(user.serviceconsent)

        return Response(consent.data, status=status_code)

    @censor_and_decorate
    def destroy(self, request, *args, **kwargs):
        try:
            response = self.get_serializer_by_request(request.user.serviceconsent).data
        except ServiceConsent.DoesNotExist:
            raise NotFound

        request.user.soft_delete()
        user_id = request.user.id
        deleted_service_cleanup.delay(
            user_id,
            response["consent"],
            history_kwargs={"user_info": user_info(user_id=user_id, channel=request.channels_permit.bundle_id)},
        )
        return Response(response)

    def _add_consent(self, user: CustomUser, consent_data: dict, service: bool = False) -> dict:
        try:
            consent = self.get_serializer_by_request(data={"user": user.id, **consent_data})
            consent.is_valid(raise_exception=True)
            consent.save()
        except ValidationError:
            # Only mark false if customer user was created via the service endpoint.
            if service:
                user.soft_delete()
            raise ParseError

        return consent


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
            except ValueError as e:
                raise ParseError(str(e))

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
        pcard_hash: t.Optional[str] = None
        pcard_pk: t.Optional[int] = None

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

        just_created = False
        pcard, route, status_code = self.payment_card_already_exists(pcard_data, request.user)

        if route == PaymentCardRoutes.EXISTS_IN_OTHER_WALLET:
            self._add_hash(pcard_data.get("hash"), pcard)
            self._link_account_to_new_user(pcard, request.user)
            metrics_route = PaymentCardAddRoute.MULTI_WALLET

        elif route in [PaymentCardRoutes.NEW_CARD, PaymentCardRoutes.DELETED_CARD]:
            pcard = self.create_payment_card_account(pcard_data, request.user, pcard)
            self._create_payment_card_consent(consent, pcard)
            just_created = True

            if route == PaymentCardRoutes.DELETED_CARD:
                metrics_route = PaymentCardAddRoute.RETURNING
            else:
                metrics_route = PaymentCardAddRoute.NEW_CARD

        # auto link to mcards if auto_link is True or None
        if auto_link(request) is not False:
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
        return self.request.channels_permit.scheme_account_query(
            SchemeAccount.objects.select_related("scheme"), user_id=self.request.user.id, user_filter=True
        )

    @censor_and_decorate
    def retrieve(self, request, *args, **kwargs):
        account = self.get_object()
        entries = request.user.schemeaccountentry_set.all()
        mcard_user_auth_status_map = {entry.scheme_account_id: entry.auth_status for entry in entries}

        return Response(self.get_serializer_by_request(
            account, context={"mcard_user_auth_status_map": mcard_user_auth_status_map}
        ).data)

    def log_update(self, scheme_account_id):
        try:
            request_patch_fields = self.request.data["account"]
            request_fields = {k: [x["column"] for x in v] for k, v in request_patch_fields.items()}
            logger.debug(
                f"Received membership card patch request for scheme account: {scheme_account_id}. "
                f"Requested fields to update: {request_fields}."
            )
        except (KeyError, ValueError, TypeError) as e:
            logger.info(f"Failed to log membership card patch request. Error: {repr(e)}")

    @censor_and_decorate
    def update(self, request, *args, **kwargs):
        account = self.get_object()
        self.log_update(account.pk)
        scheme = account.scheme
        scheme_questions = scheme.questions.all()
        update_fields, registration_fields = self._collect_updated_answers(scheme, scheme_questions)

        if registration_fields:
            registration_fields = detect_and_handle_escaped_unicode(registration_fields)
            updated_account = self._handle_registration_route(
                request.user, request.channels_permit, account, scheme, registration_fields, scheme_questions
            )
            metrics_route = MembershipCardAddRoute.REGISTER
        else:
            if update_fields:
                update_fields = detect_and_handle_escaped_unicode(update_fields)

            updated_account = self._handle_update_fields(account, scheme, update_fields, scheme_questions)
            metrics_route = MembershipCardAddRoute.UPDATE

        if metrics_route:
            membership_card_update_counter.labels(
                channel=request.channels_permit.bundle_id, scheme=scheme.slug, route=metrics_route.value
            ).inc()

        entries = request.user.schemeaccountentry_set.all()
        mcard_user_auth_status_map = {entry.scheme_account_id: entry.auth_status for entry in entries}
        return Response(
            self.get_serializer_by_request(
                updated_account, context={"mcard_user_auth_status_map": mcard_user_auth_status_map}
            ).data, status=status.HTTP_200_OK
        )

    def _handle_update_fields(
            self, account: SchemeAccount, scheme: Scheme, update_fields: dict, scheme_questions: list
    ) -> SchemeAccount:
        if "consents" in update_fields:
            del update_fields["consents"]

        manual_question_type = None
        for question in scheme_questions:
            if question.manual_question:
                manual_question_type = question.type

        if (
                manual_question_type
                and manual_question_type in update_fields
                and self.card_with_same_data_already_exists(account, scheme.id, update_fields[manual_question_type])
        ):
            account.status = account.FAILED_UPDATE
            account.save()
            return account

        self.update_credentials(account, update_fields, scheme_questions)

        account.set_pending()
        async_balance.delay(account.id, delete_balance=True)
        return account

    @staticmethod
    def _handle_registration_route(
            user: CustomUser,
            permit: Permit,
            account: SchemeAccount,
            scheme: Scheme,
            registration_fields: dict,
            scheme_questions: list,
    ) -> SchemeAccount:
        journey = SchemeAccountJourney.REGISTER.value
        HISTORY_CONTEXT.journey = journey
        check_join_with_pay(registration_fields, user.id)
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
        account.set_async_join_status()
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
        )
        return account

    @censor_and_decorate
    def replace(self, request, *args, **kwargs):
        account = self.get_object()
        if auto_link(request):
            payment_cards_to_link = PaymentCardAccountEntry.objects.filter(user_id=request.user.id).values_list(
                "payment_card_account_id", flat=True
            )
        else:
            payment_cards_to_link = []

        if account.status in [SchemeAccount.PENDING, SchemeAccount.JOIN_ASYNC_IN_PROGRESS]:
            raise ParseError("requested card is still in a pending state, please wait for current journey to finish")

        scheme, auth_fields, enrol_fields, add_fields = self._collect_fields_and_determine_route()

        if not request.channels_permit.is_scheme_available(scheme.id):
            raise ParseError("membership plan not allowed for this user.")

        # This check needs to be done before balance is deleted
        user_id = request.user.id
        if enrol_fields:
            check_join_with_pay(enrol_fields, user_id)

        account.delete_saved_balance()
        account.delete_cached_balance()

        entries = request.user.schemeaccountentry_set.all()

        if enrol_fields:
            self._replace_with_enrol_fields(request, account, enrol_fields, scheme, payment_cards_to_link)
            metrics_route = MembershipCardAddRoute.ENROL
        else:
            metrics_route = self._replace_add_and_auth_fields(
                account, add_fields, auth_fields, scheme, payment_cards_to_link, entries
            )

        if metrics_route:
            membership_card_update_counter.labels(
                channel=request.channels_permit.bundle_id,
                scheme=scheme.slug,
                route=metrics_route.value,
            ).inc()

        mcard_user_auth_status_map = {entry.scheme_account_id: entry.auth_status for entry in entries}
        return Response(
            self.get_serializer_by_request(
                account, context={"mcard_user_auth_status_map": mcard_user_auth_status_map}
            ).data, status=status.HTTP_200_OK
        )

    @staticmethod
    def _replace_with_enrol_fields(
            req: "Request", account: SchemeAccount, enrol_fields: dict, scheme: Scheme, payment_cards_to_link: list
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
        account.main_answer = ""
        if answer_types:
            if len(answer_types) > 1:
                raise ParseError("Only one type of main answer should be provided")
            account.main_answer = validated_data[answer_types.pop()]

        account.schemeaccountcredentialanswer_set.all().delete()
        account.set_async_join_status(commit_change=False)
        account.save(update_fields=["status", "main_answer"])
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

    def _replace_add_and_auth_fields(
        self,
        account: SchemeAccount,
        add_fields: dict,
        auth_fields: dict,
        scheme: Scheme,
        payment_cards_to_link: list,
        entries: 'QuerySet[SchemeAccountEntry]'
    ) -> t.Optional[MembershipCardAddRoute]:
        if auth_fields:
            auth_fields = detect_and_handle_escaped_unicode(auth_fields)

        new_answers, main_answer = self._get_new_answers(add_fields, auth_fields)

        if self.card_with_same_data_already_exists(account, scheme.id, main_answer):
            metrics_route = None
            account.status = account.FAILED_UPDATE
            account.save()
        else:
            metrics_route = MembershipCardAddRoute.UPDATE
            self.replace_credentials_and_scheme(account, new_answers, scheme)
            account.update_barcode_and_card_number()
            account.set_pending()
            async_balance.delay(account.id)

            if payment_cards_to_link:
                auto_link_membership_to_payments.delay(payment_cards_to_link, account.id)

        return metrics_route

    @censor_and_decorate
    def destroy(self, request, *args, **kwargs):
        scheme_account = self.get_object()
        if scheme_account.status in SchemeAccount.JOIN_PENDING:
            error = {"join_pending": "Membership card cannot be deleted until the Join process has completed."}
            return Response(error, status=status.HTTP_405_METHOD_NOT_ALLOWED)

        SchemeAccountEntry.objects.filter(scheme_account=scheme_account, user=request.user).delete()
        deleted_membership_card_cleanup.delay(
            scheme_account.id,
            arrow.utcnow().format(),
            request.user.id,
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
                field_type = label_to_type[item["column"]]
                self._filter_sensitive_fields(field_content, encrypted_fields, field_type, item, api_version)

            if encrypted_fields:
                field_content.update(
                    self._decrypt_sensitive_fields(self.request.channels_permit.bundle_id, encrypted_fields)
                )
        except (TypeError, KeyError, ValueError) as e:
            logger.debug(f"Error collecting field content - {type(e)} {e.args[0]}")
            raise ParseError

        return field_content

    @staticmethod
    def _decrypt_sensitive_fields(bundle_id: str, fields: dict) -> dict:
        if needs_decryption(fields.values()):
            rsa_key_pem = get_key(bundle_id=bundle_id, key_type=KeyType.PRIVATE_KEY)
            try:
                decrypted_values = zip(fields.keys(), rsa_decrypt_base64(rsa_key_pem, list(fields.values())))
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

    def _collect_updated_answers(
            self, scheme: Scheme, scheme_questions: list
    ) -> t.Tuple[t.Optional[dict], t.Optional[dict]]:
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

    def _collect_fields_and_determine_route(self) -> t.Tuple[Scheme, dict, dict, dict]:

        try:
            if not self.request.channels_permit.is_scheme_available(int(self.request.data["membership_plan"])):
                raise ParseError("membership plan not allowed for this user.")

            scheme = Scheme.get_scheme_and_questions_by_scheme_id(self.request.data["membership_plan"])

            if not self.request.channels_permit.permit_test_access(scheme):
                raise ParseError("membership plan not allowed for this user.")

        except KeyError:
            raise ParseError("required field membership_plan is missing")
        except (ValueError, Scheme.DoesNotExist):
            raise ParseError

        add_fields, auth_fields, enrol_fields = self._collect_credentials_answers(self.request.data, scheme=scheme)
        return scheme, auth_fields, enrol_fields, add_fields

    def _handle_existing_scheme_account(
        self,
        scheme_account: SchemeAccount,
        user: CustomUser,
        auth_fields: dict,
        payment_cards_to_link: list
    ) -> None:
        """This function assumes that auth fields are always provided"""
        if scheme_account.status == SchemeAccount.WALLET_ONLY:
            scheme_account.update_barcode_and_card_number()
            scheme_account.set_pending()
            SchemeAccountEntry.update_or_create_link(
                user=user, scheme_account=scheme_account, auth_status=SchemeAccountEntry.AUTHORISED
            )
            async_link.delay(auth_fields, scheme_account.id, user.id, payment_cards_to_link)
        else:
            existing_answers = scheme_account.get_auth_credentials()
            self._validate_auth_fields(auth_fields, existing_answers)

            SchemeAccountEntry.update_or_create_link(
                user=user, scheme_account=scheme_account, auth_status=SchemeAccountEntry.AUTHORISED
            )
            if payment_cards_to_link:
                auto_link_membership_to_payments(
                    payment_cards_to_link,
                    scheme_account,
                    history_kwargs={
                        "user_info": user_info(user_id=user.id, channel=self.request.channels_permit.bundle_id)
                    },
                )

    @staticmethod
    def _validate_auth_fields(auth_fields, existing_answers):
        for question_type, existing_value in existing_answers.items():
            provided_value = auth_fields.get(question_type)

            if provided_value and question_type in DATE_TYPE_CREDENTIALS:
                try:
                    provided_value = arrow.get(provided_value, "DD/MM/YYYY").date()
                except ParseError:
                    provided_value = arrow.get(provided_value).date()

                existing_value = arrow.get(existing_value).date()

            elif (
                    question_type not in CASE_SENSITIVE_CREDENTIALS
                    and isinstance(provided_value, str)
                    and isinstance(existing_value, str)
            ):

                if question_type == POSTCODE:
                    provided_value = "".join(provided_value.upper().split())
                    existing_value = "".join(existing_value.upper().split())
                else:
                    provided_value = provided_value.lower()
                    existing_value = existing_value.lower()

            if provided_value != existing_value:
                raise ParseError("This card already exists, but the provided credentials do not match.")

    def _handle_create_link_route(
        self,
        user: CustomUser,
        scheme: Scheme,
        auth_fields: dict,
        add_fields: dict,
        payment_cards_to_link: list
    ) -> t.Tuple[SchemeAccount, int, MembershipCardAddRoute]:
        history_journey = SchemeAccountJourney.ADD.value
        HISTORY_CONTEXT.journey = history_journey
        link_consents = add_fields.get("consents", []) + auth_fields.get("consents", [])
        if add_fields:
            add_fields["consents"] = link_consents
        if auth_fields:
            auth_fields["consents"] = link_consents

        serializer = self.get_serializer(data={"scheme": scheme.id, "order": 0, **add_fields})
        serializer.is_valid(raise_exception=True)

        scheme_account, _, account_created = self.create_account_with_valid_data(serializer, user, scheme)
        return_status = status.HTTP_201_CREATED if account_created else status.HTTP_200_OK

        if account_created and auth_fields:
            scheme_account.update_barcode_and_card_number()
            history_kwargs = {
                "user_info": user_info(
                    user_id=self.request.channels_permit.user.id, channel=self.request.channels_permit.bundle_id
                ),
                "journey": history_journey,
            }
            if scheme.tier in Scheme.TRANSACTION_MATCHING_TIERS:
                metrics_route = MembershipCardAddRoute.LINK
            else:
                metrics_route = MembershipCardAddRoute.WALLET_ONLY

            SchemeAccountEntry.create_link(user, scheme_account, auth_status=SchemeAccountEntry.AUTHORISED)
            async_link.delay(auth_fields, scheme_account.id, user.id, payment_cards_to_link, history_kwargs)
        elif not auth_fields:
            metrics_route = MembershipCardAddRoute.WALLET_ONLY
            self._handle_add_fields_only_link(user, scheme_account, payment_cards_to_link, account_created)
        else:
            metrics_route = MembershipCardAddRoute.MULTI_WALLET
            auth_fields = auth_fields or {}
            self._handle_existing_scheme_account(scheme_account, user, auth_fields, payment_cards_to_link)

        return scheme_account, return_status, metrics_route

    @staticmethod
    def _handle_create_join_route(
            user: CustomUser, channels_permit: Permit, scheme: Scheme, enrol_fields: dict, payment_cards_to_link: list
    ) -> t.Tuple[SchemeAccount, int]:
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
        main_answer = ""
        if answer_types:
            if len(answer_types) > 1:
                raise ParseError("Only one type of main answer should be provided")
            main_answer = enrol_fields[answer_types.pop()]

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

            other_accounts = SchemeAccount.objects.filter(
                scheme_id=scheme.id,
                schemeaccountcredentialanswer__answer=email,
            )
            if other_accounts.exists():
                scheme_account = other_accounts.first()
                SchemeAccountEntry.objects.get_or_create(
                    scheme_account=scheme_account,
                    user=user,
                )
                return scheme_account, status.HTTP_201_CREATED

        scheme_account = SchemeAccount(
            order=0, scheme_id=scheme.id, status=SchemeAccount.JOIN_ASYNC_IN_PROGRESS, main_answer=main_answer
        )

        validated_data, serializer, _ = SchemeAccountJoinMixin.validate(
            data=enrol_fields,
            scheme_account=scheme_account,
            user=user,
            permit=channels_permit,
            join_scheme=scheme,
        )

        scheme_account.save()
        SchemeAccountEntry.objects.create(
            user=user, scheme_account=scheme_account, auth_status=SchemeAccountEntry.AUTHORISED
        )
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
        return scheme_account, status.HTTP_201_CREATED

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

    def _collect_credentials_answers(
            self, data: dict, scheme: Scheme
    ) -> t.Tuple[t.Optional[dict], t.Optional[dict], t.Optional[dict]]:
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
            raise ParseError()

        if fields["enrol_fields"]:
            return None, None, fields["enrol_fields"]

        if not fields["add_fields"] and scheme.authorisation_required:
            manual_question = self._get_manual_question(scheme.slug, scheme_questions)

            try:
                fields["add_fields"].update({manual_question: fields["authorise_fields"].pop(manual_question)})
            except KeyError:
                raise ParseError()

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
    def _handle_add_fields_only_link(
        user: 'CustomUser',
        scheme_account: 'SchemeAccount',
        payment_cards_to_link: list,
        account_created: bool,
    ) -> None:
        """Handles scheme accounts for when only add fields are provided."""
        if account_created:
            scheme_account.status = SchemeAccount.WALLET_ONLY
            scheme_account.save(update_fields=["status"])
            logger.info(f"Set SchemeAccount (id={scheme_account.id}) to Wallet Only status")

        scheme_account.update_barcode_and_card_number()
        SchemeAccountEntry.create_link(
            user=user, scheme_account=scheme_account, auth_status=SchemeAccountEntry.UNAUTHORISED
        )

        if payment_cards_to_link:
            auto_link_membership_to_payments(payment_cards_to_link, scheme_account)

    @staticmethod
    def match_consents(consent_links, data_provided):
        consent_labels = {link.consent_label for link in consent_links}
        data_keys = {data["column"] for data in data_provided}

        return data_keys.intersection(consent_labels)

    @staticmethod
    def allowed_answers(scheme: Scheme) -> t.List[str]:
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
        accounts = self.filter_queryset(self.get_queryset()).exclude(status=SchemeAccount.JOIN)

        entries = request.user.schemeaccountentry_set.all()
        mcard_user_auth_status_map = {entry.scheme_account_id: entry.auth_status for entry in entries}

        response = self.get_serializer_by_request(
            accounts, many=True, context={"mcard_user_auth_status_map": mcard_user_auth_status_map}
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
            account, status_code = self._handle_create_join_route(
                request.user, request.channels_permit, scheme, enrol_fields, payment_cards_to_link
            )
        else:
            if auth_fields:
                auth_fields = detect_and_handle_escaped_unicode(auth_fields)

            account, status_code, metrics_route = self._handle_create_link_route(
                request.user, scheme, auth_fields, add_fields, payment_cards_to_link
            )

        if scheme.slug in settings.SCHEMES_COLLECTING_METRICS:
            send_merchant_metrics_for_new_account.delay(request.user.id, account.id, account.scheme.slug)

        if metrics_route:
            membership_card_add_counter.labels(
                channel=request.channels_permit.bundle_id, scheme=scheme.slug, route=metrics_route.value
            ).inc()

        entries = request.user.schemeaccountentry_set.all()
        mcard_user_auth_status_map = {entry.scheme_account_id: entry.auth_status for entry in entries}

        return Response(
            self.get_serializer_by_request(
                account,
                context={
                    "request": request,
                    "mcard_user_auth_status_map": mcard_user_auth_status_map
                }
            ).data,
            status=status_code
        )


class CardLinkView(VersionedSerializerMixin, ModelViewSet):
    authentication_classes = (PropertyAuthentication,)

    @censor_and_decorate
    def update_payment(self, request, *args, **kwargs):
        self.response_serializer = SelectSerializer.PAYMENT_CARD
        link, status_code = self._update_link(request.user, kwargs["pcard_id"], kwargs["mcard_id"])
        link.payment_card_account.refresh_from_db(fields=["pll_links"])
        serializer = self.get_serializer_by_request(link.payment_card_account)
        return Response(serializer.data, status_code)

    @censor_and_decorate
    def update_membership(self, request, *args, **kwargs):
        self.response_serializer = SelectSerializer.MEMBERSHIP_CARD
        link, status_code = self._update_link(request.user, kwargs["pcard_id"], kwargs["mcard_id"])
        link.scheme_account.refresh_from_db(fields=["pll_links"])
        serializer = self.get_serializer_by_request(link.scheme_account)
        return Response(serializer.data, status_code)

    @censor_and_decorate
    def destroy_payment(self, request, *args, **kwargs):
        pcard, _ = self._destroy_link(request.user, kwargs["pcard_id"], kwargs["mcard_id"])
        return Response({}, status.HTTP_200_OK)

    @censor_and_decorate
    def destroy_membership(self, request, *args, **kwargs):
        _, mcard = self._destroy_link(request.user, kwargs["pcard_id"], kwargs["mcard_id"])
        return Response({}, status.HTTP_200_OK)

    def _destroy_link(
            self, user: CustomUser, pcard_id: int, mcard_id: int
    ) -> t.Tuple[PaymentCardAccount, SchemeAccount]:
        pcard, mcard = self._collect_cards(pcard_id, mcard_id, user)

        try:
            link = PaymentCardSchemeEntry.objects.get(scheme_account=mcard, payment_card_account=pcard)
        except PaymentCardSchemeEntry.DoesNotExist:
            raise NotFound("The link that you are trying to delete does not exist.")
        # Check that if the Payment card has visa slug (VOP) and that the card is not linked to same merchant
        # in list with activated status - if so call deactivate and then delete link
        activations = VopActivation.find_activations_matching_links([link])
        link.delete()
        PaymentCardSchemeEntry.deactivate_activations(activations)
        return pcard, mcard

    def _update_link(self, user: CustomUser, pcard_id: int, mcard_id: int) -> t.Tuple[PaymentCardSchemeEntry, int]:
        pcard, mcard = self._collect_cards(pcard_id, mcard_id, user)
        status_code = status.HTTP_200_OK

        try:
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
            )
        except PaymentCardSchemeEntry.DoesNotExist:
            link = PaymentCardSchemeEntry(
                scheme_account=mcard, payment_card_account=pcard
            ).get_instance_with_active_status()
            link.save()
            link.vop_activate_check()
            status_code = status.HTTP_201_CREATED
            audit.write_to_db(link)

        return link, status_code

    @staticmethod
    def _collect_cards(
            payment_card_id: int, membership_card_id: int, user: CustomUser
    ) -> t.Tuple[PaymentCardAccount, SchemeAccount]:
        try:
            filters = {"is_deleted": False}
            payment_card = user.payment_card_account_set.get(pk=payment_card_id, **filters)
            membership_card = user.scheme_account_set.get(
                pk=membership_card_id,
                **filters
            )

        except PaymentCardAccount.DoesNotExist:
            raise NotFound(f"The payment card of id {payment_card_id} was not found.")
        except SchemeAccount.DoesNotExist:
            raise NotFound(f"The membership card of id {membership_card_id} was not found or is not authorised.")
        except KeyError:
            raise ParseError

        return payment_card, membership_card


# TODO: these endpoints are not in spec and will be removed later on
# class CompositeMembershipCardView(ListMembershipCardView):
#     authentication_classes = (PropertyAuthentication,)
#     response_serializer = SelectSerializer.MEMBERSHIP_CARD
#
#     def get_queryset(self):
#         query = {
#             'payment_card_account_set__id': self.kwargs['pcard_id']
#         }
#
#         if not self.request.user.is_tester:
#             query['scheme__test_scheme'] = False
#
#         return self.request.channels_permit.scheme_account_query(
#             SchemeAccount.objects.filter(**query),
#             user_id=self.request.user.id,
#             user_filter=True
#         )
#
#     @censor_and_decorate
#     def list(self, request, *args, **kwargs):
#         accounts = self.filter_queryset(self.get_queryset())
#         return Response(self.get_serializer_by_request(accounts, many=True).data)
#
#     @censor_and_decorate
#     def create(self, request, *args, **kwargs):
#         pcard = get_object_or_404(PaymentCardAccount, pk=kwargs['pcard_id'])
#         scheme_id, auth_fields, enrol_fields, add_fields = self._collect_fields_and_determine_route()
#         if enrol_fields:
#             account, status_code = self._handle_create_join_route(request.user, request.channels_permit,
#                                                                   scheme_id, enrol_fields)
#         else:
#             account, status_code = self._handle_create_link_route(request.user, scheme_id, auth_fields,
#                                                                   add_fields)
#         PaymentCardSchemeEntry.objects.get_or_create(payment_card_account=pcard, scheme_account=account)
#         return Response(self.get_serializer_by_request(
#         account, context={'request': request}).data, status=status_code)

# class CompositePaymentCardView(ListCreatePaymentCardAccount, VersionedSerializerMixin, PaymentCardCreationMixin,
#                                ModelViewSet):
#     authentication_classes = (PropertyAuthentication,)
#     serializer_class = PaymentCardSerializer
#     response_serializer = SelectSerializer.PAYMENT_CARD
#
#     def get_queryset(self):
#         query = {
#             'user_set__id': self.request.user.pk,
#             'scheme_account_set__id': self.kwargs['mcard_id'],
#             'is_deleted': False
#         }
#
#         return self.request.channels_permit.scheme_payment_account_query(PaymentCardAccount.objects.filter(**query))
#
#     @censor_and_decorate
#     def create(self, request, *args, **kwargs):
#         try:
#             pcard_data = self.get_serializer_by_version(
#                 SelectSerializer.PAYMENT_CARD_TRANSLATION,
#                 get_api_version(request),
#                 request.data['card'],
#                 context={'bundle_id': request.channels_permit.bundle_id}
#             ).data
#
#             if self.allowed_issuers and int(pcard_data['issuer']) not in self.allowed_issuers:
#                 raise ParseError('issuer not allowed for this user.')
#
#             consent = request.data['account']['consents']
#         except (KeyError, ValueError):
#             raise ParseError
#
#         exists, pcard, status_code = self.payment_card_already_exists(pcard_data, request.user)
#         if exists:
#             return Response(self.get_serializer_by_request(pcard).data, status=status_code)
#
#         mcard = get_object_or_404(SchemeAccount, pk=kwargs['mcard_id'])
#         message, status_code, pcard = self.create_payment_card_account(pcard_data, request.user)
#         if status_code == status.HTTP_201_CREATED:
#             PaymentCardSchemeEntry.objects.get_or_create(payment_card_account=pcard, scheme_account=mcard)
#             pcard = self._create_payment_card_consent(consent, pcard)
#             return Response(self.get_serializer_by_request(pcard).data, status=status_code)
#
#         return Response(message, status=status_code)


class MembershipPlanView(VersionedSerializerMixin, ModelViewSet):
    authentication_classes = (PropertyAuthentication,)
    serializer_class = MembershipPlanSerializer
    response_serializer = SelectSerializer.MEMBERSHIP_PLAN

    def get_queryset(self):
        return self.request.channels_permit.scheme_query(Scheme.objects)

    @CacheApiRequest("m_plans", settings.REDIS_MPLANS_CACHE_EXPIRY, membership_plan_key)
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

    @CacheApiRequest("m_plans", settings.REDIS_MPLANS_CACHE_EXPIRY, membership_plan_key)
    @censor_and_decorate
    def list(self, request, *args, **kwargs):
        self.serializer_class = self.get_serializer_class_by_request()
        return super().list(request, *args, **kwargs)

    @censor_and_decorate
    def identify(self, request):
        try:
            base64_image = request.data["card"]["base64_image"]
        except KeyError:
            raise ParseError

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
        url = "{}/transactions/user/{}".format(settings.HADES_URL, request.user.id)
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
        transactions = (
            request.channels_permit.scheme_account_query(
                SchemeAccount.objects.filter(id=kwargs["mcard_id"]), user_id=request.user.id, user_filter=True
            )
            .values_list("transactions", flat=True)
            .first()
        )
        return Response(transactions or [])

    @staticmethod
    def _account_belongs_to_user(request: "Request", mcard_id: int) -> bool:
        return request.channels_permit.scheme_account_query(
            SchemeAccount.objects.filter(id=mcard_id), user_id=request.user.id, user_filter=True
        ).exists()
