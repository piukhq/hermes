import logging
import re
import typing as t
from functools import partial
from pathlib import Path

import arrow
import requests
import sentry_sdk
from azure.storage.blob import BlockBlobService
from django.conf import settings
from django.db import IntegrityError
from django.db.models import Q, Count
from requests import request
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound, ParseError, ValidationError, APIException
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rustyjeff import rsa_decrypt_base64
from shared_config_storage.credentials.encryption import BLAKE2sHash
from shared_config_storage.credentials.utils import AnswerTypeChoices

import analytics
from hermes.channel_vault import KeyType, get_key, get_secret_key, SecretKeyName
from hermes.channels import Permit
from hermes.settings import Version
from payment_card import metis
from payment_card.enums import PaymentCardRoutes
from payment_card.models import PaymentCardAccount
from payment_card.payment import get_nominated_pcard
from payment_card.views import ListCreatePaymentCardAccount, RetrievePaymentCardAccount
from scheme.credentials import DATE_TYPE_CREDENTIALS, PAYMENT_CARD_HASH
from scheme.mixins import (BaseLinkMixin, IdentifyCardMixin, SchemeAccountCreationMixin, UpdateCredentialsMixin,
                           SchemeAccountJoinMixin)
from scheme.models import Scheme, SchemeAccount, SchemeCredentialQuestion, ThirdPartyConsentLink
from scheme.views import RetrieveDeleteAccount
from ubiquity.authentication import PropertyAuthentication, PropertyOrServiceAuthentication
from ubiquity.cache_decorators import CacheApiRequest, membership_plan_key
from ubiquity.censor_empty_fields import censor_and_decorate
from ubiquity.influx_audit import audit
from ubiquity.models import PaymentCardAccountEntry, PaymentCardSchemeEntry, SchemeAccountEntry, ServiceConsent
from ubiquity.tasks import (async_link, async_all_balance, async_join, async_registration, async_balance,
                            send_merchant_metrics_for_new_account, send_merchant_metrics_for_link_delete,
                            async_add_field_only_link, deleted_payment_card_cleanup)
from ubiquity.versioning import versioned_serializer_class, SelectSerializer, get_api_version
from ubiquity.versioning.base.serializers import (MembershipCardSerializer, MembershipPlanSerializer,
                                                  PaymentCardConsentSerializer, PaymentCardReplaceSerializer,
                                                  PaymentCardSerializer, MembershipTransactionsMixin,
                                                  PaymentCardUpdateSerializer, ServiceConsentSerializer,
                                                  TransactionSerializer, LinkMembershipCardSerializer)
from user.models import CustomUser
from user.serializers import UbiquityRegisterSerializer

if t.TYPE_CHECKING:
    from django.http import HttpResponse
    from rest_framework.serializers import Serializer

escaped_unicode_pattern = re.compile(r'\\(\\u[a-fA-F0-9]{4})')
logger = logging.getLogger(__name__)


class ConflictError(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'Attempting to create two or more identical users at the same time.'
    default_code = 'conflict'


def is_auto_link(req):
    return (req.query_params.get('autoLink', '').lower() == 'true' or
            req.query_params.get('autolink', '').lower() == 'true')


def replace_escaped_unicode(match):
    return match.group(1)


def detect_and_handle_escaped_unicode(credentials_dict):
    # Fix for Barclays sending escaped unicode sequences for special chars in password.
    if credentials_dict.get("password"):
        password = credentials_dict["password"]
        if password.isascii():
            password = escaped_unicode_pattern.sub(
                replace_escaped_unicode, password
            ).encode().decode("unicode-escape")

        credentials_dict["password"] = password

    return credentials_dict


def send_data_to_atlas(response: 'HttpResponse') -> None:
    url = f"{settings.ATLAS_URL}/audit/ubiquity_user/save"
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Token {}'.format(settings.SERVICE_API_KEY)
    }
    data = {
        'email': response['consent']['email'],
        'ubiquity_join_date': arrow.get(response['consent']['timestamp']).format("YYYY-MM-DD hh:mm:ss")
    }
    request("POST", url=url, headers=headers, json=data)


def check_join_with_pay(enrol_fields: dict, user_id: int):
    payment_card_hash = enrol_fields.get(PAYMENT_CARD_HASH)
    if payment_card_hash:
        try:
            get_nominated_pcard(payment_card_hash, user_id)
        except PaymentCardAccount.DoesNotExist as e:
            raise ParseError(detail="Provided payment card could not be found "
                                    "or is not related to this user") from e


class VersionedSerializerMixin:

    @staticmethod
    def get_serializer_by_version(serializer: SelectSerializer, version: 'Version', *args, **kwargs) -> 'Serializer':
        serializer_class = versioned_serializer_class(version, serializer)
        return serializer_class(*args, **kwargs)

    def get_serializer_by_request(self, *args, **kwargs):
        version = get_api_version(self.request)
        serializer_class = versioned_serializer_class(version, self.response_serializer)
        context = kwargs.get('context', {})
        context.update(self.get_serializer_context())
        kwargs['context'] = context
        return serializer_class(*args, **kwargs)

    def get_serializer_class_by_request(self):
        version = get_api_version(self.request)
        return versioned_serializer_class(version, self.response_serializer)


class AutoLinkOnCreationMixin:

    @staticmethod
    def auto_link_to_payment_cards(user: CustomUser, account: SchemeAccount) -> None:
        query = {
            'user': user
        }
        payment_card_ids = {
            pcard['payment_card_account_id']
            for pcard in PaymentCardAccountEntry.objects.values('payment_card_account_id').filter(**query)
        }

        if payment_card_ids:
            query = {
                'scheme_account__scheme_id': account.scheme_id,
                'payment_card_account_id__in': payment_card_ids
            }
            excluded = {
                pcard['payment_card_account_id']
                for pcard in PaymentCardSchemeEntry.objects.values('payment_card_account_id').filter(**query)
            }
            payment_card_to_link = payment_card_ids.difference(excluded)
            scheme_account_id = account.id

            for pcard_id in payment_card_to_link:
                PaymentCardSchemeEntry(
                    scheme_account_id=scheme_account_id,
                    payment_card_account_id=pcard_id
                ).get_instance_with_active_status().save()

    @staticmethod
    def auto_link_to_membership_cards(user: CustomUser,
                                      account: PaymentCardAccount,
                                      just_created: bool = False) -> None:

        # Ensure that we only consider membership cards in a user's wallet which can be PLL linked
        wallet_scheme_accounts = SchemeAccount.objects.values('id', 'scheme_id').filter(
            user_set=user, scheme__tier=Scheme.PLL
        )

        # Get Membership Card Plans (scheme id) use all wallets which are linked to this Payment Card.
        already_linked_scheme_ids = []

        if not just_created:
            already_linked_scheme_ids = [
                entry['scheme_account__scheme_id']
                for entry in
                PaymentCardSchemeEntry.objects.values('scheme_account__scheme_id').filter(
                    payment_card_account_id=account.id)
            ]

        # Golden rule is that a payment card can only be linked to one membership plan via any relevant membership card
        # because in matching a payment card transaction the linked account must only be credited once ie only one
        # link must be set. If there are many cards in a wallet with the same plan and not previously linked
        # the preference will be to choose the oldest ie the lowest id.
        # Once a link is set it is never changed for an older card or for a card in another wallet.

        cards_by_scheme_ids = {}
        instances_to_bulk_create = {}

        for wsa in wallet_scheme_accounts:
            scheme_account_id = wsa['id']
            scheme_id = wsa['scheme_id']
            # link instance will only be save if in instances_to_bulk_create
            link = PaymentCardSchemeEntry(scheme_account_id=scheme_account_id, payment_card_account=account)
            if scheme_id not in already_linked_scheme_ids:
                # we have a potential new link to a scheme account which does not have a previously linked plan
                if cards_by_scheme_ids.get(scheme_id):
                    # however, this scheme account which is a link candidate so we must choose the oldest (lowest id)
                    # Todo confirm if we should we choose the lowest id which is active or the lowest id if none active
                    #  at the time of auto-linking ie where x is current if statement
                    #  (x and (link.active_link or not instances_to_bulk_create[scheme_id].active_link) or
                    #  (link.active_link and not instances_to_bulk_create[scheme_id].active_link):
                    if cards_by_scheme_ids[scheme_id] > scheme_account_id:
                        cards_by_scheme_ids[scheme_id] = scheme_account_id
                        instances_to_bulk_create[scheme_id] = link.get_instance_with_active_status()
                else:
                    cards_by_scheme_ids[scheme_id] = scheme_account_id
                    instances_to_bulk_create[scheme_id] = link.get_instance_with_active_status()

        for link in instances_to_bulk_create.values():
            link.save()


class PaymentCardCreationMixin:

    @staticmethod
    def _create_payment_card_consent(consent_data: dict, pcard: PaymentCardAccount) -> PaymentCardAccount:
        serializer = PaymentCardConsentSerializer(data=consent_data, many=True)
        serializer.is_valid(raise_exception=True)
        pcard.refresh_from_db()
        pcard.consents = serializer.validated_data
        pcard.save()
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
    def payment_card_already_exists(data: dict, user: CustomUser) -> t.Tuple[
        t.Optional[PaymentCardAccount],
        PaymentCardRoutes,
        int
    ]:
        status_code = status.HTTP_201_CREATED
        card = PaymentCardAccount.all_objects.filter(
            fingerprint=data['fingerprint']
        ).annotate(
            belongs_to_this_user=Count('user_set', filter=Q(user_set__id=user.id))
        ).order_by(
            '-belongs_to_this_user', 'is_deleted', '-created'
        ).first()

        if card is None:
            route = PaymentCardRoutes.NEW_CARD
        elif card.is_deleted:
            route = PaymentCardRoutes.DELETED_CARD
        elif card.belongs_to_this_user:
            route = PaymentCardRoutes.ALREADY_IN_WALLET
            status_code = status.HTTP_200_OK
        elif card.expiry_month == data['expiry_month'] and card.expiry_year == data['expiry_year']:
            route = PaymentCardRoutes.EXISTS_IN_OTHER_WALLET
        else:
            route = PaymentCardRoutes.NEW_CARD

        return card, route, status_code

    @staticmethod
    def _add_hash(new_hash: str, card: PaymentCardAccount) -> None:
        if new_hash and not card.hash:
            card.hash = new_hash
            card.save()

    @staticmethod
    def _link_account_to_new_user(account: PaymentCardAccount, user: CustomUser) -> None:
        if account.is_deleted:
            account.is_deleted = False
            account.save()

        PaymentCardAccountEntry.objects.get_or_create(user=user, payment_card_account=account)
        for scheme_account in account.scheme_account_set.all():
            SchemeAccountEntry.objects.get_or_create(user=user, scheme_account=scheme_account)

    @staticmethod
    def _collect_creation_data(request_data: dict, allowed_issuers: t.List[int], version: 'Version',
                               bundle_id: str = None) -> t.Tuple[dict, dict]:
        try:
            pcard_data = VersionedSerializerMixin.get_serializer_by_version(
                SelectSerializer.PAYMENT_CARD_TRANSLATION,
                version,
                request_data['card'],
                context={'bundle_id': bundle_id}
            ).data

            if allowed_issuers and int(pcard_data['issuer']) not in allowed_issuers:
                raise ParseError('issuer not allowed for this user.')

            consent = request_data['account']['consents']
        except (KeyError, ValueError) as e:
            logger.debug(f"error creating payment card: {repr(e)}")
            raise ParseError from e

        return pcard_data, consent


class AllowedIssuersMixin:
    stored_allowed_issuers = None

    @property
    def allowed_issuers(self):
        if self.stored_allowed_issuers is None:
            self.stored_allowed_issuers = list(
                self.request.channels_permit.bundle.issuer.values_list('id', flat=True)
            )

        return self.stored_allowed_issuers


class ServiceView(VersionedSerializerMixin, ModelViewSet):
    authentication_classes = (PropertyOrServiceAuthentication,)
    serializer_class = ServiceConsentSerializer
    response_serializer = SelectSerializer.SERVICE

    @censor_and_decorate
    def retrieve(self, request, *args, **kwargs):
        async_all_balance.delay(request.user.id, self.request.channels_permit)
        return Response(
            self.get_serializer_by_request(request.user.serviceconsent).data
        )

    @censor_and_decorate
    def create(self, request, *args, **kwargs):
        status_code = 200
        consent_data = request.data['consent']
        if 'email' not in consent_data:
            raise ParseError

        try:
            if request.channels_permit.auth_by == 'bink':
                user = request.channels_permit.user
            else:
                user = CustomUser.objects.get(client=request.channels_permit.client, external_id=request.prop_id)
        except CustomUser.DoesNotExist:
            new_user_data = {
                'client_id': request.channels_permit.client.pk,
                'bundle_id': request.channels_permit.bundle_id,
                'email': consent_data['email'],
                'external_id': request.prop_id
            }
            status_code = 201
            new_user = UbiquityRegisterSerializer(data=new_user_data, context={'bearer_registration': True})
            new_user.is_valid(raise_exception=True)

            try:
                user = new_user.save()
            except IntegrityError:
                raise ConflictError

            consent = self._add_consent(user, consent_data)
        else:
            if not hasattr(user, 'serviceconsent'):
                status_code = 201
                consent = self._add_consent(user, consent_data)

            else:
                consent = self.get_serializer_by_request(user.serviceconsent)

        return Response(consent.data, status=status_code)

    @censor_and_decorate
    def destroy(self, request, *args, **kwargs):
        try:
            response = self.get_serializer_by_request(request.user.serviceconsent).data
            request.user.serviceconsent.delete()
        except ServiceConsent.DoesNotExist:
            raise NotFound

        self._delete_membership_cards(request.user)
        self._delete_payment_cards(request.user)

        request.user.soft_delete()

        try:  # send user info to be persisted in Atlas
            send_data_to_atlas(response)
        except Exception:
            sentry_sdk.capture_exception()
        return Response(response)

    def _add_consent(self, user: CustomUser, consent_data: dict) -> dict:
        try:
            consent = self.get_serializer_by_request(data={'user': user.id, **consent_data})
            consent.is_valid(raise_exception=True)
            consent.save()
        except ValidationError:
            user.is_active = False
            user.save()
            raise ParseError

        return consent

    @staticmethod
    def _delete_membership_cards(user: CustomUser) -> None:
        cards_to_delete = []
        cards_to_unlink = []
        for card in user.scheme_account_set.all():
            if card.user_set.count() == 1:
                cards_to_delete.append(card.id)

            cards_to_unlink.append(card.id)

        PaymentCardSchemeEntry.objects.filter(scheme_account_id__in=cards_to_delete).delete()
        SchemeAccount.objects.filter(id__in=cards_to_delete).update(is_deleted=True)
        SchemeAccountEntry.objects.filter(user_id=user.id, scheme_account_id__in=cards_to_unlink).delete()

    @staticmethod
    def _delete_payment_cards(user: CustomUser) -> None:
        cards_to_delete = []
        cards_to_unlink = []
        for card in user.payment_card_account_set.all():
            if card.user_set.count() == 1:
                cards_to_delete.append(card.id)
                metis.delete_payment_card(card)

            cards_to_unlink.append(card.id)

        PaymentCardSchemeEntry.objects.filter(scheme_account_id__in=cards_to_delete).delete()
        PaymentCardAccount.objects.filter(id__in=cards_to_delete).update(is_deleted=True)
        PaymentCardAccountEntry.objects.filter(user_id=user.id, payment_card_account_id__in=cards_to_unlink).delete()


class PaymentCardView(RetrievePaymentCardAccount, VersionedSerializerMixin, PaymentCardCreationMixin,
                      AutoLinkOnCreationMixin, AllowedIssuersMixin, ModelViewSet):
    authentication_classes = (PropertyAuthentication,)
    serializer_class = PaymentCardSerializer
    response_serializer = SelectSerializer.PAYMENT_CARD

    def get_queryset(self):
        query = {}
        if self.allowed_issuers:
            query['issuer__in'] = self.allowed_issuers

        return self.request.channels_permit.payment_card_account_query(
            PaymentCardAccount.objects.filter(**query),
            user_id=self.request.user.id,
            user_filter=True
        )

    def get_hashed_object(self):
        if self.kwargs.get('hash'):
            self.kwargs['hash'] = BLAKE2sHash().new(
                obj=self.kwargs['hash'],
                key=get_secret_key(SecretKeyName.PCARD_HASH_SECRET)
            )
        return super(PaymentCardView, self).get_object()

    @censor_and_decorate
    def retrieve(self, request, *args, **kwargs):
        self.serializer_class = self.get_serializer_class_by_request()
        return super().retrieve(request, *args, **kwargs)

    @censor_and_decorate
    def update(self, request, *args, **kwargs):
        if 'card' in request.data:
            try:
                data = PaymentCardUpdateSerializer(request.data['card']).data
                PaymentCardAccount.objects.filter(pk=kwargs['pk']).update(**data)
            except ValueError as e:
                raise ParseError(str(e))

        if 'account' in request.data and 'consents' in request.data['account']:
            self._update_payment_card_consent(request.data['account']['consents'], kwargs['pk'])

        pcard = get_object_or_404(PaymentCardAccount, pk=kwargs['pk'])
        return Response(self.get_serializer_by_request(pcard).data)

    @censor_and_decorate
    def replace(self, request, *args, **kwargs):
        account = self.get_object()
        pcard_data, consent = self._collect_creation_data(
            request_data=request.data,
            allowed_issuers=self.allowed_issuers,
            version=get_api_version(request),
            bundle_id=request.channels_permit.bundle_id
        )
        if pcard_data['fingerprint'] != account.fingerprint:
            raise ParseError('cannot override fingerprint.')

        pcard_data['token'] = account.token
        new_card_data = PaymentCardReplaceSerializer(data=pcard_data)
        new_card_data.is_valid(raise_exception=True)
        PaymentCardAccount.objects.filter(pk=account.pk).update(**new_card_data.validated_data)
        # todo should we replace the consent too?

        account.refresh_from_db()

        if is_auto_link(request):
            self.auto_link_to_membership_cards(request.user, account)

        return Response(self.get_serializer_by_request(account).data, status.HTTP_200_OK)

    @censor_and_decorate
    def destroy(self, request, *args, **kwargs):
        query = {'user_id': request.user.id}
        pcard_hash: t.Optional[str] = None
        pcard_pk: t.Optional[int] = None

        if self.kwargs.get('hash'):
            pcard_hash = BLAKE2sHash().new(
                obj=self.kwargs['hash'],
                key=get_secret_key(SecretKeyName.PCARD_HASH_SECRET)
            )
            query['payment_card_account__hash'] = pcard_hash
        else:
            pcard_pk = kwargs['pk']
            query['payment_card_account_id'] = pcard_pk

        get_object_or_404(PaymentCardAccountEntry.objects, **query).delete()
        deleted_payment_card_cleanup.delay(pcard_pk, pcard_hash)
        return Response({}, status=status.HTTP_200_OK)


class ListPaymentCardView(ListCreatePaymentCardAccount, VersionedSerializerMixin, PaymentCardCreationMixin,
                          AutoLinkOnCreationMixin, AllowedIssuersMixin, ModelViewSet):
    authentication_classes = (PropertyAuthentication,)
    serializer_class = PaymentCardSerializer
    response_serializer = SelectSerializer.PAYMENT_CARD

    def get_queryset(self):
        query = {}
        if self.allowed_issuers:
            query['issuer__in'] = self.allowed_issuers

        return self.request.channels_permit.payment_card_account_query(
            PaymentCardAccount.objects.filter(**query),
            user_id=self.request.user.id,
            user_filter=True
        )

    @staticmethod
    def serialize_pcard(serializer, account):
        data = serializer(account).data
        return data

    @censor_and_decorate
    def list(self, request, *args, **kwargs):
        accounts = list(self.filter_queryset(self.get_queryset()))

        if len(accounts) >= 2:
            serialize_account = partial(
                self.serialize_pcard,
                self.get_serializer_class_by_request()
            )
            with settings.THREAD_POOL_EXECUTOR(max_workers=settings.THREAD_POOL_EXECUTOR_MAX_WORKERS) as executor:
                response = list(executor.map(serialize_account, accounts))
        else:
            response = self.get_serializer_by_request(accounts, many=True).data

        return Response(response, status=200)

    @censor_and_decorate
    def create(self, request, *args, **kwargs):
        pcard_data, consent = self._collect_creation_data(
            request_data=request.data,
            allowed_issuers=self.allowed_issuers,
            version=get_api_version(request),
            bundle_id=request.channels_permit.bundle_id
        )

        auto_link = is_auto_link(request)
        just_created = False
        pcard, route, status_code = self.payment_card_already_exists(pcard_data, request.user)

        if route == PaymentCardRoutes.EXISTS_IN_OTHER_WALLET:
            self._add_hash(pcard_data.get('hash'), pcard)
            self._link_account_to_new_user(pcard, request.user)

        elif route in [PaymentCardRoutes.NEW_CARD, PaymentCardRoutes.DELETED_CARD]:
            pcard = self.create_payment_card_account(pcard_data, request.user, pcard)
            self._create_payment_card_consent(consent, pcard)
            just_created = True

        if auto_link:
            self.auto_link_to_membership_cards(request.user, pcard, just_created)

        return Response(self.get_serializer_by_request(pcard).data, status=status_code)


class MembershipCardView(RetrieveDeleteAccount, VersionedSerializerMixin, UpdateCredentialsMixin, BaseLinkMixin,
                         SchemeAccountCreationMixin, SchemeAccountJoinMixin, AutoLinkOnCreationMixin, ModelViewSet):
    authentication_classes = (PropertyAuthentication,)
    response_serializer = SelectSerializer.MEMBERSHIP_CARD
    override_serializer_classes = {
        'GET': MembershipCardSerializer,
        'PATCH': MembershipCardSerializer,
        'DELETE': MembershipCardSerializer,
        'PUT': LinkMembershipCardSerializer
    }
    create_update_fields = ('add_fields', 'authorise_fields', 'registration_fields', 'enrol_fields')

    def get_queryset(self):
        query = {}
        if not self.request.user.is_tester:
            query['scheme__test_scheme'] = False

        return self.request.channels_permit.scheme_account_query(
            SchemeAccount.objects.filter(
                **query
            ).select_related('scheme'),
            user_id=self.request.user.id,
            user_filter=True
        )

    def get_validated_data(self, data: dict, user, scheme=None):
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)

        # my360 schemes should never come through this endpoint
        if not scheme:
            scheme = Scheme.objects.get(id=data['scheme'])

        if scheme.url == settings.MY360_SCHEME_URL:
            metadata = {
                'scheme name': scheme.name,
            }
            if user.client_id == settings.BINK_CLIENT_ID:
                analytics.post_event(
                    user,
                    analytics.events.MY360_APP_EVENT,
                    metadata,
                    True
                )

            raise serializers.ValidationError({
                "non_field_errors": [
                    "Invalid Scheme: {}. Please use /schemes/accounts/my360 endpoint".format(scheme.slug)
                ]
            })
        return serializer

    @censor_and_decorate
    def retrieve(self, request, *args, **kwargs):
        account = self.get_object()
        return Response(self.get_serializer_by_request(account).data)

    def log_update(self, scheme_account_id):
        try:
            request_patch_fields = self.request.data['account']
            request_fields = {k: [x['column'] for x in v] for k, v in request_patch_fields.items()}
            logger.debug(f'Received membership card patch request for scheme account: {scheme_account_id}. '
                         f'Requested fields to update: {request_fields}.')
        except (KeyError, ValueError, TypeError) as e:
            logger.info(f'Failed to log membership card patch request. Error: {repr(e)}')

    @censor_and_decorate
    def update(self, request, *args, **kwargs):
        account = self.get_object()
        self.log_update(account.pk)
        scheme = account.scheme
        scheme_questions = scheme.questions.all().values()
        update_fields, registration_fields = self._collect_updated_answers(scheme, scheme_questions)

        if registration_fields:
            registration_fields = detect_and_handle_escaped_unicode(registration_fields)
            updated_account = self._handle_registration_route(request.user, request.channels_permit,
                                                              account, registration_fields, scheme_questions)
        else:
            if update_fields:
                update_fields = detect_and_handle_escaped_unicode(update_fields)

            updated_account = self._handle_update_fields(account, update_fields, scheme_questions)

        return Response(self.get_serializer_by_request(updated_account).data, status=status.HTTP_200_OK)

    def _handle_update_fields(self, account: SchemeAccount, update_fields: dict, scheme_questions: list
                              ) -> SchemeAccount:
        if 'consents' in update_fields:
            del update_fields['consents']

        manual_question_type = None
        for question in scheme_questions:
            if question["manual_question"]:
                manual_question_type = question["type"]

        card_with_same_data_already_exists = self.card_with_same_data_already_exists(
            account,
            account.scheme_id,
            update_fields[manual_question_type]
        )

        if manual_question_type and manual_question_type in update_fields and card_with_same_data_already_exists:
            account.status = account.FAILED_UPDATE
            account.save()
            return account

        self.update_credentials(account, update_fields, scheme_questions)

        account.set_pending()
        async_balance.delay(account.id, delete_balance=True)
        return account

    @staticmethod
    def _handle_registration_route(user: CustomUser, permit: Permit, account: SchemeAccount,
                                   registration_fields: dict, scheme_questions: list) -> SchemeAccount:
        check_join_with_pay(registration_fields, user.id)
        manual_answer = account.card_number
        if manual_answer:
            main_credential = manual_answer
            question_type = [question["type"] for question in scheme_questions if question["manual_question"]][0]
        else:
            main_credential = account.barcode
            question_type = [question["type"] for question in scheme_questions if question["scan_question"]][0]
        registration_data = {
            question_type: main_credential,
            **registration_fields,
            'scheme_account': account
        }
        validated_data, serializer, _ = SchemeAccountJoinMixin.validate(
            data=registration_data,
            scheme_account=account,
            user=user,
            permit=permit,
            scheme_id=account.scheme_id
        )
        account.set_async_join_status()
        async_registration.delay(user.id, serializer, account.id, validated_data, delete_balance=True)
        return account

    @censor_and_decorate
    def replace(self, request, *args, **kwargs):
        account = self.get_object()
        if account.status in [SchemeAccount.PENDING, SchemeAccount.JOIN_ASYNC_IN_PROGRESS]:
            raise ParseError('requested card is still in a pending state, please wait for current journey to finish')

        scheme, auth_fields, enrol_fields, add_fields, _ = self._collect_fields_and_determine_route()

        if not request.channels_permit.is_scheme_available(scheme.id):
            raise ParseError('membership plan not allowed for this user.')

        # This check needs to be done before balance is deleted
        user_id = request.user.id
        if enrol_fields:
            check_join_with_pay(enrol_fields, user_id)

        account.delete_saved_balance()
        account.delete_cached_balance()

        if enrol_fields:
            enrol_fields = detect_and_handle_escaped_unicode(enrol_fields)
            validated_data, serializer, _ = SchemeAccountJoinMixin.validate(
                data=enrol_fields,
                scheme_account=account,
                user=request.user,
                permit=request.channels_permit,
                scheme_id=account.scheme_id
            )
            account.schemeaccountcredentialanswer_set.all().delete()
            account.main_answer = ""
            account.set_async_join_status()
            async_join.delay(account.id, user_id, serializer, scheme.id, validated_data)

        else:
            if auth_fields:
                auth_fields = detect_and_handle_escaped_unicode(auth_fields)

            new_answers, main_answer = self._get_new_answers(add_fields, auth_fields)

            if self.card_with_same_data_already_exists(account, scheme.id, main_answer):
                account.status = account.FAILED_UPDATE
                account.save()
            else:
                self.replace_credentials_and_scheme(account, new_answers, scheme)
                account.update_barcode_and_card_number()
                account.set_pending()
                async_balance.delay(account.id)

        if is_auto_link(request):
            self.auto_link_to_payment_cards(request.user, account)

        return Response(self.get_serializer_by_request(account).data, status=status.HTTP_200_OK)

    @censor_and_decorate
    def destroy(self, request, *args, **kwargs):
        scheme_account = self.get_object()
        scheme_slug = scheme_account.scheme.slug
        scheme_account_id = scheme_account.id
        delete_date = arrow.utcnow().format()

        pll_links = PaymentCardSchemeEntry.objects.filter(scheme_account_id=scheme_account_id)
        entries_query = SchemeAccountEntry.objects.filter(scheme_account_id=scheme_account_id)

        if scheme_account.user_set.count() <= 1:
            scheme_account.is_deleted = True
            scheme_account.save(update_fields=['is_deleted'])

            if request.user.client_id == settings.BINK_CLIENT_ID:
                analytics.update_scheme_account_attribute(
                    scheme_account,
                    request.user,
                    old_status=dict(scheme_account.STATUSES).get(scheme_account.status_key))

        else:
            m_card_users = scheme_account.user_set.exclude(id=request.user.id).values_list('id', flat=True)
            pll_links = pll_links.exclude(payment_card_account__user_set__id__in=m_card_users)
            entries_query = entries_query.filter(user_id=request.user.id)

        entries_query.delete()
        pll_links.delete()

        if scheme_slug in settings.SCHEMES_COLLECTING_METRICS:
            send_merchant_metrics_for_link_delete.delay(scheme_account_id, scheme_slug, delete_date, 'delete')

        return Response({}, status=status.HTTP_200_OK)

    @censor_and_decorate
    def membership_plan(self, request, mcard_id):
        mcard = get_object_or_404(SchemeAccount, id=mcard_id)
        context = self.get_serializer_context()
        self.response_serializer = SelectSerializer.MEMBERSHIP_PLAN
        return Response(self.get_serializer_by_request(mcard.scheme, context=context).data)

    def _collect_field_content(self, fields_type, data, label_to_type):
        try:
            fields = data['account'].get(fields_type, [])
            api_version = get_api_version(self.request)
            field_content = {}
            encrypted_fields = {}

            for item in fields:
                field_type = label_to_type[item['column']]
                self._filter_sensitive_fields(field_content, encrypted_fields, field_type, item, api_version)

            if encrypted_fields:
                field_content.update(
                    self._decrypt_sensitive_fields(
                        self.request.channels_permit.bundle_id,
                        encrypted_fields
                    )
                )
        except (TypeError, KeyError, ValueError) as e:
            logger.debug(f"Error collecting field content - {type(e)} {e.args[0]}")
            raise ParseError

        return field_content

    @staticmethod
    def _decrypt_sensitive_fields(bundle_id: str, fields: dict) -> dict:
        rsa_key_pem = get_key(
            bundle_id=bundle_id,
            key_type=KeyType.PRIVATE_KEY
        )
        try:
            decrypted_values = zip(fields.keys(), rsa_decrypt_base64(rsa_key_pem, list(fields.values())))
        except ValueError as e:
            raise ValueError("Failed to decrypt sensitive feilds") from e

        fields.update(decrypted_values)
        return fields

    @staticmethod
    def _filter_sensitive_fields(field_content: dict, encrypted_fields: dict, field_type: dict, item: dict,
                                 api_version: Version) -> None:
        credential_type = field_type['type']
        answer_type = field_type['answer_type']

        if api_version >= Version.v1_2 and answer_type == AnswerTypeChoices.SENSITIVE.value:
            encrypted_fields[credential_type] = item['value']
        else:
            field_content[credential_type] = item['value']

    def _collect_updated_answers(self, scheme: Scheme, scheme_questions: list
                                 ) -> t.Tuple[t.Optional[dict], t.Optional[dict]]:
        data = self.request.data
        label_to_type = scheme.get_question_type_dict(scheme_questions)
        out_fields = {}
        for fields_type in self.create_update_fields:
            out_fields[fields_type] = self._extract_consent_data(scheme, fields_type, data)
            out_fields[fields_type].update(self._collect_field_content(fields_type, data, label_to_type))

        if not out_fields or out_fields['enrol_fields']:
            raise ParseError

        if out_fields['registration_fields']:
            return None, out_fields['registration_fields']

        return {**out_fields['add_fields'], **out_fields['authorise_fields']}, None

    def _collect_fields_and_determine_route(self) -> t.Tuple[Scheme, dict, dict, dict, list]:

        try:
            if not self.request.channels_permit.is_scheme_available(int(self.request.data['membership_plan'])):
                raise ParseError('membership plan not allowed for this user.')

            scheme = Scheme.objects.get(pk=self.request.data['membership_plan'])
            scheme_questions = scheme.questions.all()
            if not self.request.user.is_tester and scheme.test_scheme:
                raise ParseError('membership plan not allowed for this user.')

        except KeyError:
            raise ParseError('required field membership_plan is missing')
        except (ValueError, Scheme.DoesNotExist):
            raise ParseError
        add_fields, auth_fields, enrol_fields = self._collect_credentials_answers(
            self.request.data, scheme=scheme, scheme_questions=scheme_questions.values()
        )
        return scheme, auth_fields, enrol_fields, add_fields, scheme_questions

    @staticmethod
    def _handle_existing_scheme_account(scheme_account: SchemeAccount, user: CustomUser,
                                        auth_fields: dict) -> None:
        existing_answers = scheme_account.get_auth_fields()
        for k, v in existing_answers.items():
            provided_value = auth_fields.get(k)

            if provided_value and k in DATE_TYPE_CREDENTIALS:
                try:
                    provided_value = arrow.get(provided_value, 'DD/MM/YYYY').date()
                except ParseError:
                    provided_value = arrow.get(provided_value).date()

                v = arrow.get(v).date()

            if provided_value != v:
                raise ParseError('This card already exists, but the provided credentials do not match.')

        SchemeAccountEntry.objects.get_or_create(user=user, scheme_account=scheme_account)

    def _handle_create_link_route(self, user: CustomUser, scheme: Scheme, auth_fields: dict, add_fields: dict
                                  ) -> t.Tuple[SchemeAccount, int]:

        data = {'scheme': scheme.id, 'order': 0, **add_fields}
        serializer = self.get_validated_data(data, user, scheme=scheme)
        scheme_account, _, account_created = self.create_account_with_valid_data(serializer, user)
        return_status = status.HTTP_201_CREATED if account_created else status.HTTP_200_OK
        scheme_account.update_barcode_and_card_number(self.scheme_questions)

        if auth_fields:
            if account_created:
                scheme_account.set_pending()
                async_link.delay(auth_fields, scheme_account.id, user.id)
            else:
                auth_fields = auth_fields or {}
                self._handle_existing_scheme_account(scheme_account, user, auth_fields)
        else:
            scheme_account.set_pending()
            async_add_field_only_link.delay(scheme_account.id)

        return scheme_account, return_status

    @staticmethod
    def _handle_create_join_route(user: CustomUser, channels_permit: Permit, scheme: Scheme, enrol_fields: dict
                                  ) -> t.Tuple[SchemeAccount, int]:
        check_join_with_pay(enrol_fields, user.id)
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

        newly_created = False
        try:
            scheme_account = SchemeAccount.objects.get(
                user_set__id=user.id,
                scheme_id=scheme.id,
                status__in=SchemeAccount.JOIN_ACTION_REQUIRED
            )
            scheme_account.set_async_join_status()
        except SchemeAccount.DoesNotExist:
            newly_created = True
            scheme_account = SchemeAccount(
                order=0,
                scheme_id=scheme.id,
                status=SchemeAccount.JOIN_ASYNC_IN_PROGRESS
            )

        validated_data, serializer, _ = SchemeAccountJoinMixin.validate(
            data=enrol_fields,
            scheme_account=scheme_account,
            user=user,
            permit=channels_permit,
            scheme_id=scheme.id,
        )

        if newly_created:
            scheme_account.save()
            SchemeAccountEntry.objects.get_or_create(user=user, scheme_account=scheme_account)

        async_join.delay(scheme_account.id, user.id, serializer, scheme.id, validated_data)
        return scheme_account, status.HTTP_201_CREATED

    @staticmethod
    def _manual_check_csv_creation(add_fields: dict) -> None:
        email, *_ = add_fields.values()

        if settings.MANUAL_CHECK_USE_AZURE:
            csv_name = '{}{}_{}'.format(settings.MANUAL_CHECK_AZURE_FOLDER, arrow.utcnow().format('DD_MM_YYYY'),
                                        settings.MANUAL_CHECK_AZURE_CSV_FILENAME)

            blob_storage = BlockBlobService(settings.MANUAL_CHECK_AZURE_ACCOUNT_NAME,
                                            settings.MANUAL_CHECK_AZURE_ACCOUNT_KEY)
            if blob_storage.exists(settings.MANUAL_CHECK_AZURE_CONTAINER, csv_name):
                current = blob_storage.get_blob_to_text(settings.MANUAL_CHECK_AZURE_CONTAINER, csv_name).content
            else:
                current = '"email","authorised (yes, no, pending)"'

            current += '\n"{}",pending'.format(email)
            blob_storage.create_blob_from_text(settings.MANUAL_CHECK_AZURE_CONTAINER, csv_name, current)
        else:
            if not Path(settings.MANUAL_CHECK_CSV_PATH).exists():
                with open(settings.MANUAL_CHECK_CSV_PATH, 'w') as f:
                    f.write('"email","authorised (yes, no, pending)"')

            with open(settings.MANUAL_CHECK_CSV_PATH, 'a') as f:
                f.write('\n"{}",pending'.format(email))

    @staticmethod
    def _get_manual_question(scheme_slug, scheme_questions):
        for question in scheme_questions:
            if question["manual_question"]:
                return question["type"]

        raise SchemeCredentialQuestion.DoesNotExist(
            f'could not find the manual question for scheme: {scheme_slug}.'
        )

    def _collect_credentials_answers(self, data: dict, scheme: Scheme, scheme_questions: list
                                     ) -> t.Tuple[t.Optional[dict], t.Optional[dict], t.Optional[dict]]:

        try:
            label_to_type = scheme.get_question_type_dict(scheme_questions)
            fields = {}

            for field_name in self.create_update_fields:
                fields[field_name] = self._extract_consent_data(scheme, field_name, data)
                fields[field_name].update(self._collect_field_content(field_name, data, label_to_type))

        except (KeyError, ValueError) as e:
            logger.exception(e)
            raise ParseError()

        if fields['enrol_fields']:
            return None, None, fields['enrol_fields']

        if not fields['add_fields'] and scheme.authorisation_required:
            manual_question = self._get_manual_question(scheme.slug, scheme_questions)

            try:
                fields['add_fields'].update({manual_question: fields['authorise_fields'].pop(manual_question)})
            except KeyError:
                raise ParseError()

        elif not fields['add_fields']:
            raise ParseError('missing fields')

        return fields['add_fields'], fields['authorise_fields'], None

    def _extract_consent_data(self, scheme: Scheme, field: str, data: dict) -> dict:
        if not data['account'].get(field):
            return {}

        client_app = self.request.channels_permit.client
        data_provided = data['account'][field]

        consent_links = ThirdPartyConsentLink.objects.filter(scheme=scheme, client_app=client_app)
        provided_consent_keys = self.match_consents(consent_links, data_provided)

        if not provided_consent_keys:
            return {'consents': []}

        provided_consent_data = {
            item['column']: item for item in data_provided if item['column'] in provided_consent_keys
        }

        consents = [
            {
                'id': link.consent_id,
                'value': provided_consent_data[link.consent_label]['value']
            }
            for link in consent_links if provided_consent_data.get(link.consent_label)
        ]

        # remove consents information from provided credentials data
        data['account'][field] = [item for item in data_provided if item['column'] not in provided_consent_keys]

        return {'consents': consents}

    @staticmethod
    def match_consents(consent_links, data_provided):
        consent_labels = {link.consent_label for link in consent_links}
        data_keys = {data['column'] for data in data_provided}

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
    override_serializer_classes = {
        'GET': MembershipCardSerializer,
        'POST': LinkMembershipCardSerializer
    }

    @censor_and_decorate
    def list(self, request, *args, **kwargs):
        accounts = list(self.filter_queryset(self.get_queryset()).exclude(status=SchemeAccount.JOIN))
        response = self.get_serializer_by_request(accounts, many=True).data
        return Response(response, status=200)

    @censor_and_decorate
    def create(self, request, *args, **kwargs):
        scheme, auth_fields, enrol_fields, add_fields, scheme_questions = self._collect_fields_and_determine_route()
        self.current_scheme = scheme
        self.scheme_questions = scheme_questions

        if enrol_fields:
            enrol_fields = detect_and_handle_escaped_unicode(enrol_fields)
            account, status_code = self._handle_create_join_route(
                request.user, request.channels_permit, scheme, enrol_fields
            )
        else:
            if auth_fields:
                auth_fields = detect_and_handle_escaped_unicode(auth_fields)

            account, status_code = self._handle_create_link_route(
                request.user, scheme, auth_fields, add_fields
            )

        if is_auto_link(request):
            self.auto_link_to_payment_cards(request.user, account)

        if scheme.slug in settings.SCHEMES_COLLECTING_METRICS:
            send_merchant_metrics_for_new_account.delay(request.user.id, account.id, account.scheme.slug)

        return Response(self.get_serializer_by_request(account, context={'request': request}).data, status=status_code)


class CardLinkView(VersionedSerializerMixin, ModelViewSet):
    authentication_classes = (PropertyAuthentication,)

    @censor_and_decorate
    def update_payment(self, request, *args, **kwargs):
        self.response_serializer = SelectSerializer.PAYMENT_CARD
        link, status_code = self._update_link(request.user, kwargs['pcard_id'], kwargs['mcard_id'])
        serializer = self.get_serializer_by_request(link.payment_card_account)
        return Response(serializer.data, status_code)

    @censor_and_decorate
    def update_membership(self, request, *args, **kwargs):
        self.response_serializer = SelectSerializer.MEMBERSHIP_CARD
        link, status_code = self._update_link(request.user, kwargs['pcard_id'], kwargs['mcard_id'])
        serializer = self.get_serializer_by_request(link.scheme_account)
        return Response(serializer.data, status_code)

    @censor_and_decorate
    def destroy_payment(self, request, *args, **kwargs):
        pcard, _ = self._destroy_link(request.user, kwargs['pcard_id'], kwargs['mcard_id'])
        return Response({}, status.HTTP_200_OK)

    @censor_and_decorate
    def destroy_membership(self, request, *args, **kwargs):
        _, mcard = self._destroy_link(request.user, kwargs['pcard_id'], kwargs['mcard_id'])
        return Response({}, status.HTTP_200_OK)

    def _destroy_link(self, user: CustomUser, pcard_id: int, mcard_id: int
                      ) -> t.Tuple[PaymentCardAccount, SchemeAccount]:
        pcard, mcard = self._collect_cards(pcard_id, mcard_id, user)

        try:
            link = PaymentCardSchemeEntry.objects.get(scheme_account=mcard, payment_card_account=pcard)
        except PaymentCardSchemeEntry.DoesNotExist:
            raise NotFound('The link that you are trying to delete does not exist.')

        link.delete()
        return pcard, mcard

    def _update_link(self, user: CustomUser, pcard_id: int, mcard_id: int) -> t.Tuple[PaymentCardSchemeEntry, int]:
        pcard, mcard = self._collect_cards(pcard_id, mcard_id, user)
        status_code = status.HTTP_200_OK
        link, created = PaymentCardSchemeEntry.objects.get_or_create(scheme_account=mcard, payment_card_account=pcard)
        if created:
            status_code = status.HTTP_201_CREATED

        link.activate_link()
        audit.write_to_db(link)
        return link, status_code

    @staticmethod
    def _collect_cards(payment_card_id: int, membership_card_id: int,
                       user: CustomUser) -> t.Tuple[PaymentCardAccount, SchemeAccount]:
        try:
            filters = {'is_deleted': False}
            payment_card = user.payment_card_account_set.get(pk=payment_card_id, **filters)

            if not user.is_tester:
                filters['scheme__test_scheme'] = False

            membership_card = user.scheme_account_set.get(pk=membership_card_id, **filters)

        except PaymentCardAccount.DoesNotExist:
            raise NotFound('The payment card of id {} was not found.'.format(payment_card_id))
        except SchemeAccount.DoesNotExist:
            raise NotFound('The membership card of id {} was not found.'.format(membership_card_id))
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
        queryset = Scheme.objects

        if not self.request.user.is_tester:
            queryset = queryset.filter(test_scheme=False)

        return self.request.channels_permit.scheme_query(queryset)

    @CacheApiRequest('m_plans', settings.REDIS_MPLANS_CACHE_EXPIRY, membership_plan_key)
    @censor_and_decorate
    def retrieve(self, request, *args, **kwargs):
        self.serializer_class = self.get_serializer_class_by_request()
        return super().retrieve(request, *args, **kwargs)


class ListMembershipPlanView(VersionedSerializerMixin, ModelViewSet, IdentifyCardMixin):
    authentication_classes = (PropertyAuthentication,)
    serializer_class = MembershipPlanSerializer
    response_serializer = SelectSerializer.MEMBERSHIP_PLAN

    def get_queryset(self):
        queryset = Scheme.objects

        if not self.request.user.is_tester:
            queryset = queryset.filter(test_scheme=False)

        return self.request.channels_permit.scheme_query(queryset)

    @CacheApiRequest('m_plans', settings.REDIS_MPLANS_CACHE_EXPIRY, membership_plan_key)
    @censor_and_decorate
    def list(self, request, *args, **kwargs):
        self.serializer_class = self.get_serializer_class_by_request()
        return super().list(request, *args, **kwargs)

    @censor_and_decorate
    def identify(self, request):
        try:
            base64_image = request.data['card']['base64_image']
        except KeyError:
            raise ParseError

        json = self._get_scheme(base64_image)
        if json['status'] != 'success' or json['reason'] == 'no match':
            return Response({'status': 'failure', 'message': json['reason']}, status=400)

        scheme = get_object_or_404(Scheme, id=json['scheme_id'])
        return Response(self.get_serializer_by_request(scheme).data)


class MembershipTransactionView(ModelViewSet, VersionedSerializerMixin, MembershipTransactionsMixin):
    authentication_classes = (PropertyAuthentication,)
    serializer_class = TransactionSerializer
    response_serializer = SelectSerializer.MEMBERSHIP_TRANSACTION

    @censor_and_decorate
    def retrieve(self, request, *args, **kwargs):
        url = '{}/transactions/{}'.format(settings.HADES_URL, kwargs['transaction_id'])
        headers = {'Authorization': self._get_auth_token(request.user.id), 'Content-Type': 'application/json'}
        resp = requests.get(url, headers=headers)
        resp_json = resp.json()
        if resp.status_code == 200 and resp_json:
            if isinstance(resp_json, list) and len(resp_json) > 1:
                logger.warning("Hades responded with more than one transaction for a single id")
            transaction = resp_json[0]
            serializer = self.serializer_class(data=transaction)
            serializer.is_valid(raise_exception=True)

            if self._account_belongs_to_user(request.user, serializer.initial_data.get('scheme_account_id')):
                return Response(self.get_serializer_by_request(serializer.validated_data).data)

        return Response({})

    @censor_and_decorate
    def list(self, request, *args, **kwargs):
        url = '{}/transactions/user/{}'.format(settings.HADES_URL, request.user.id)
        headers = {'Authorization': self._get_auth_token(request.user.id), 'Content-Type': 'application/json'}
        resp = requests.get(url, headers=headers)
        resp_json = resp.json()
        if resp.status_code == 200 and resp_json:
            serializer = self.serializer_class(data=resp_json, many=True, context={"user": request.user})
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data[:5]  # limit to 5 transactions as per documentation
            if data:
                return Response(self.get_serializer_by_request(data, many=True).data)

        return Response([])

    @censor_and_decorate
    def composite(self, request, *args, **kwargs):
        if not self._account_belongs_to_user(request.user, kwargs['mcard_id']):
            return Response([])

        transactions = self.get_transactions_data(request.user.id, kwargs['mcard_id'])
        serializer = self.serializer_class(data=transactions, many=True, context={"user": request.user})
        serializer.is_valid(raise_exception=True)
        return Response(self.get_serializer_by_request(serializer.validated_data, many=True).data)

    @staticmethod
    def _account_belongs_to_user(user: CustomUser, mcard_id: int) -> bool:
        query = {
            'id': mcard_id,
            'is_deleted': False
        }
        if not user.is_tester:
            query['scheme__test_scheme'] = False

        return user.scheme_account_set.filter(**query).exists()
