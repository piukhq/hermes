import logging
import re
import typing as t
import uuid
from pathlib import Path

import arrow
import sentry_sdk
from azure.storage.blob import BlockBlobService
from django.conf import settings
from requests import request
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound, ParseError, ValidationError
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

import analytics
from hermes.traced_requests import requests
from payment_card.models import PaymentCardAccount
from payment_card.views import ListCreatePaymentCardAccount, RetrievePaymentCardAccount
from scheme.credentials import DATE_TYPE_CREDENTIALS
from scheme.mixins import (BaseLinkMixin, IdentifyCardMixin, SchemeAccountCreationMixin, UpdateCredentialsMixin,
                           SchemeAccountJoinMixin)
from scheme.models import Scheme, SchemeAccount, SchemeCredentialQuestion, ThirdPartyConsentLink, ConsentStatus
from scheme.serializers import UserConsentSerializer
from scheme.views import RetrieveDeleteAccount
from ubiquity.authentication import PropertyAuthentication, PropertyOrServiceAuthentication
from ubiquity.censor_empty_fields import censor_and_decorate
from ubiquity.influx_audit import audit
from ubiquity.models import PaymentCardAccountEntry, PaymentCardSchemeEntry, SchemeAccountEntry
from ubiquity.serializers import (MembershipCardSerializer, MembershipPlanSerializer, MembershipTransactionsMixin,
                                  PaymentCardConsentSerializer, PaymentCardReplaceSerializer, PaymentCardSerializer,
                                  PaymentCardTranslationSerializer, PaymentCardUpdateSerializer,
                                  ServiceConsentSerializer, TransactionsSerializer,
                                  LinkMembershipCardSerializer)
from ubiquity.tasks import async_link, async_all_balance, async_join, async_registration, async_balance
from user.models import CustomUser
from user.serializers import UbiquityRegisterSerializer
from hermes.channels import Permit

if t.TYPE_CHECKING:
    from django.http import HttpResponse

escaped_unicode_pattern = re.compile(r'\\(\\u[a-fA-F0-9]{4})')
logger = logging.getLogger(__name__)


def replace_escaped_unicode(match):
    return match.group(1).encode().decode('unicode-escape')


def send_data_to_atlas(response: 'HttpResponse') -> None:
    url = f"{settings.ATLAS_URL}/ubiquity_user/save"
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Token {}'.format(settings.SERVICE_API_KEY)
    }
    data = {
        'email': response['consent']['email'],
        'ubiquity_join_date': arrow.get(response['consent']['timestamp']).format("YYYY-MM-DD hh:mm:ss")
    }
    request("POST", url=url, headers=headers, json=data)


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

            PaymentCardSchemeEntry.objects.bulk_create([
                PaymentCardSchemeEntry(scheme_account_id=scheme_account_id, payment_card_account_id=pcard_id)
                for pcard_id in payment_card_to_link
            ])

    @staticmethod
    def auto_link_to_membership_cards(user: CustomUser, account: PaymentCardAccount) -> None:
        # not in spec for now but preparing for later
        ...


class PaymentCardCreationMixin:
    @staticmethod
    def _create_payment_card_consent(consent_data: dict, pcard: PaymentCardAccount) -> dict:
        serializer = PaymentCardConsentSerializer(data=consent_data, many=True)
        serializer.is_valid(raise_exception=True)
        pcard.consents = serializer.validated_data
        pcard.save()
        return PaymentCardSerializer(pcard).data

    @staticmethod
    def _update_payment_card_consent(consent_data: dict, pcard_pk: int) -> None:
        if not consent_data:
            consents = []
        else:
            serializer = PaymentCardConsentSerializer(data=consent_data, many=True)
            serializer.is_valid(raise_exception=True)
            consents = serializer.validated_data

        PaymentCardAccount.objects.filter(pk=pcard_pk).update(consents=consents)

    def payment_card_already_exists(self, data: dict, user: CustomUser) \
            -> t.Tuple[bool, t.Optional[SchemeAccount], t.Optional[int]]:
        query = {
            'fingerprint': data['fingerprint'],
            'expiry_month': data['expiry_month'],
            'expiry_year': data['expiry_year'],
        }
        try:
            card = PaymentCardAccount.objects.get(**query)
        except PaymentCardAccount.DoesNotExist:
            return False, None, None

        if user in card.user_set.all():
            return True, card, status.HTTP_200_OK

        self._link_account_to_new_user(card, user)
        return True, card, status.HTTP_201_CREATED

    @staticmethod
    def _link_account_to_new_user(account: PaymentCardAccount, user: CustomUser) -> None:
        if account.is_deleted:
            account.is_deleted = False
            account.save()

        PaymentCardAccountEntry.objects.get_or_create(user=user, payment_card_account=account)
        for scheme_account in account.scheme_account_set.all():
            SchemeAccountEntry.objects.get_or_create(user=user, scheme_account=scheme_account)

    @staticmethod
    def _collect_creation_data(request_data: dict, allowed_issuers: t.List[int]) -> t.Tuple[dict, dict]:
        try:
            pcard_data = PaymentCardTranslationSerializer(request_data['card']).data
            if allowed_issuers and int(pcard_data['issuer']) not in allowed_issuers:
                raise ParseError('issuer not allowed for this user.')

            consent = request_data['account']['consents']
        except (KeyError, ValueError):
            raise ParseError

        return pcard_data, consent


class ServiceView(ModelViewSet):
    authentication_classes = (PropertyOrServiceAuthentication,)
    serializer_class = ServiceConsentSerializer

    @censor_and_decorate
    def retrieve(self, request, *args, **kwargs):
        if not request.user.is_active:
            raise NotFound
        async_all_balance.delay(request.user.id, self.request.channels_permit)
        return Response(self.get_serializer(request.user.serviceconsent).data)

    @censor_and_decorate
    def create(self, request, *args, **kwargs):
        status_code = 200
        consent_data = request.data['consent']
        if 'email' not in consent_data:
            raise ParseError

        new_user_data = {
            'client_id': request.channels_permit.client.pk,
            'bundle_id': request.channels_permit.bundle_id,
            'email': consent_data['email'],
            'external_id': request.prop_id,
            'password': str(uuid.uuid4()).lower().replace('-', 'A&')
        }

        try:
            user = CustomUser.objects.get(client=request.channels_permit.client, external_id=request.prop_id)
        except CustomUser.DoesNotExist:
            status_code = 201
            new_user = UbiquityRegisterSerializer(data=new_user_data)
            new_user.is_valid(raise_exception=True)
            user = new_user.save()
            consent = self._add_consent(user, consent_data)
        else:
            if not user.is_active:
                status_code = 201
                user.is_active = True
                user.save()

                if hasattr(user, 'serviceconsent'):
                    user.serviceconsent.delete()

                consent = self._add_consent(user, consent_data)

            else:
                consent = self.get_serializer(user.serviceconsent)

        return Response(consent.data, status=status_code)

    @censor_and_decorate
    def destroy(self, request, *args, **kwargs):
        response = self.get_serializer(request.user.serviceconsent).data
        request.user.serviceconsent.delete()
        request.user.is_active = False
        request.user.save()

        try:  # send user info to be persisted in Atlas
            send_data_to_atlas(response)
        except Exception:
            sentry_sdk.capture_exception()
        return Response(response)

    def _add_consent(self, user: CustomUser, consent_data: dict) -> dict:
        try:
            consent = self.get_serializer(data={'user': user.pk, **consent_data})
            consent.is_valid(raise_exception=True)
            consent.save()
        except ValidationError:
            user.is_active = False
            user.save()
            raise ParseError

        return consent


class PaymentCardView(RetrievePaymentCardAccount, PaymentCardCreationMixin, AutoLinkOnCreationMixin, ModelViewSet):
    authentication_classes = (PropertyAuthentication,)
    serializer_class = PaymentCardSerializer

    def get_queryset(self):
        query = {
            'user_set__id': self.request.user.id,
            'is_deleted': False
        }
        if self.request.allowed_issuers:
            query['issuer__in'] = self.request.allowed_issuers

        return self.queryset.filter(**query)

    @censor_and_decorate
    def retrieve(self, request, *args, **kwargs):
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
        return Response(self.get_serializer(pcard).data)

    @censor_and_decorate
    def replace(self, request, *args, **kwargs):
        account = self.get_object()
        pcard_data, consent = self._collect_creation_data(request.data, request.allowed_issuers)
        if pcard_data['fingerprint'] != account.fingerprint:
            raise ParseError('cannot override fingerprint.')

        pcard_data['token'] = account.token
        new_card_data = PaymentCardReplaceSerializer(data=pcard_data)
        new_card_data.is_valid(raise_exception=True)
        PaymentCardAccount.objects.filter(pk=account.pk).update(**new_card_data.validated_data)
        # todo should we replace the consent too?

        account.refresh_from_db()

        if request.query_params.get('autoLink') == 'True':
            self.auto_link_to_membership_cards(request.user, account)

        return Response(self.get_serializer(account).data, status.HTTP_200_OK)

    @censor_and_decorate
    def destroy(self, request, *args, **kwargs):
        payment_card_account = self.get_object()
        p_card_users = {
            user['id'] for user in
            payment_card_account.user_set.values('id').exclude(id=request.user.id)
        }

        query = {
            'scheme_account__user_set__id__in': p_card_users
        }

        PaymentCardSchemeEntry.objects.filter(payment_card_account=payment_card_account).exclude(**query).delete()
        super().delete(request, *args, **kwargs)
        return Response({}, status=status.HTTP_200_OK)


class ListPaymentCardView(ListCreatePaymentCardAccount, PaymentCardCreationMixin, AutoLinkOnCreationMixin,
                          ModelViewSet):
    authentication_classes = (PropertyAuthentication,)
    serializer_class = PaymentCardSerializer

    def get_queryset(self):
        query = {
            'user_set__id': self.request.user.id,
            'is_deleted': False
        }
        if self.request.allowed_issuers:
            query['issuer__in'] = self.request.allowed_issuers

        return PaymentCardAccount.objects.filter(**query)

    @censor_and_decorate
    def list(self, request, *args, **kwargs):
        accounts = self.filter_queryset(self.get_queryset())
        return Response(self.get_serializer(accounts, many=True).data, status=200)

    @censor_and_decorate
    def create(self, request, *args, **kwargs):
        pcard_data, consent = self._collect_creation_data(request.data, request.allowed_issuers)
        exists, pcard, status_code = self.payment_card_already_exists(pcard_data, request.user)
        if exists:
            return Response(self.get_serializer(pcard).data, status=status_code)

        message, status_code, pcard = self.create_payment_card_account(pcard_data, request.user)
        if status_code == status.HTTP_201_CREATED:
            return Response(self._create_payment_card_consent(consent, pcard), status=status_code)

        if request.query_params.get('autoLink') == 'True':
            self.auto_link_to_membership_cards(request.user, pcard)

        return Response(self.get_serializer(pcard).data, status=status_code)


class MembershipCardView(RetrieveDeleteAccount, UpdateCredentialsMixin, SchemeAccountCreationMixin, BaseLinkMixin,
                         SchemeAccountJoinMixin, AutoLinkOnCreationMixin, ModelViewSet):
    authentication_classes = (PropertyAuthentication,)
    override_serializer_classes = {
        'GET': MembershipCardSerializer,
        'PATCH': MembershipCardSerializer,
        'DELETE': MembershipCardSerializer,
        'PUT': LinkMembershipCardSerializer
    }
    create_update_fields = ('add_fields', 'authorise_fields', 'registration_fields', 'enrol_fields')

    def get_queryset(self):
        query = {
            'user_set__id': self.request.user.id,
            'is_deleted': False
        }

        return self.request.channels_permit.scheme_account_query(SchemeAccount.objects.filter(**query))

    def get_validated_data(self, data, user):
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        # my360 schemes should never come through this endpoint
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
        return Response(self.get_serializer(account).data)

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

        update_fields, registration_fields = self._collect_updated_answers(account.scheme)
        manual_question = SchemeCredentialQuestion.objects.filter(scheme=account.scheme, manual_question=True).first()

        if registration_fields:
            updated_account = self._handle_registration_route(request.user, request.channels_permit,
                                                              account, registration_fields)
        else:
            updated_account = self._handle_update_fields(account, update_fields, manual_question.type)

        async_balance.delay(updated_account.id)
        return Response(self.get_serializer(updated_account).data, status=status.HTTP_200_OK)

    def _handle_update_fields(self, account: SchemeAccount, update_fields: dict, manual_question: str) -> SchemeAccount:
        if 'consents' in update_fields:
            del update_fields['consents']

        if update_fields.get('password'):
            # Fix for Barclays sending escaped unicode sequences for special chars.
            update_fields['password'] = escaped_unicode_pattern.sub(replace_escaped_unicode, update_fields['password'])

        if manual_question and manual_question in update_fields:
            if self.card_with_same_data_already_exists(account, account.scheme.id, update_fields[manual_question]):
                account.status = account.FAILED_UPDATE
                account.save()
                return account

        self.update_credentials(account, update_fields)
        account.delete_cached_balance()
        account.set_pending()
        return account

    @staticmethod
    def _handle_registration_route(user: CustomUser, permit: Permit, account: SchemeAccount,
                                   registration_fields: dict) -> SchemeAccount:
        account.set_async_join_status()
        async_registration.delay(user.id, permit, account.id, registration_fields)
        return account

    @staticmethod
    def save_new_consents(scheme_account, user, all_fields):
        consents = []
        for field in all_fields:
            if field is not None and 'consents' in field:
                consents = field.pop('consents')
                if consents:
                    consents.append(consents)

        user_consents = UserConsentSerializer.get_user_consents(scheme_account, consents, user)
        for user_consent in user_consents:
            user_consent.status = ConsentStatus.SUCCESS
            user_consent.save()

    @censor_and_decorate
    def replace(self, request, *args, **kwargs):
        account = self.get_object()
        scheme_id, auth_fields, enrol_fields, add_fields = self._collect_fields_and_determine_route()

        if not request.channels_permit.is_scheme_available(scheme_id):
            raise ParseError('membership plan not allowed for this user.')

        self.save_new_consents(account, self.request.user, [auth_fields, enrol_fields, add_fields])

        if enrol_fields:
            raise NotImplementedError
        else:
            new_answers, main_answer = self._get_new_answers(add_fields, auth_fields)

            if self.card_with_same_data_already_exists(account, scheme_id, main_answer):
                account.status = account.FAILED_UPDATE
                account.save()
            else:
                self.replace_credentials_and_scheme(account, new_answers, scheme_id)

        if request.query_params.get('autoLink') == 'True':
            self.auto_link_to_payment_cards(request.user, account)

        async_balance.delay(account.id)
        return Response(MembershipCardSerializer(account).data, status=status.HTTP_200_OK)

    @censor_and_decorate
    def destroy(self, request, *args, **kwargs):
        scheme_account = self.get_object()
        m_card_users = [
            user['id'] for user in
            scheme_account.user_set.values('id').exclude(id=request.user.id)
        ]

        query = {
            'payment_card_account__user_set__id__in': m_card_users
        }
        PaymentCardSchemeEntry.objects.filter(scheme_account=scheme_account).exclude(**query).delete()
        super().delete(request, *args, **kwargs)
        return Response({}, status=status.HTTP_200_OK)

    @censor_and_decorate
    def membership_plan(self, request, mcard_id):
        mcard = get_object_or_404(SchemeAccount, id=mcard_id)
        context = self.get_serializer_context()
        return Response(MembershipPlanSerializer(mcard.scheme, context=context).data)

    @staticmethod
    def _collect_field_content(field, data, label_to_type):
        try:
            return {
                label_to_type[item['column']]: item['value']
                for item in data['account'].get(field, [])
            }
        except (TypeError, KeyError):
            raise ParseError

    def _collect_updated_answers(self, scheme: Scheme) -> t.Tuple[t.Optional[dict], t.Optional[dict]]:
        data = self.request.data
        label_to_type = scheme.get_question_type_dict()
        out_fields = {}
        for field_name in self.create_update_fields:
            out_fields[field_name] = self._extract_consent_data(scheme, field_name, data)
            out_fields[field_name].update(self._collect_field_content(field_name, data, label_to_type))

        if not out_fields or out_fields['enrol_fields']:
            raise ParseError

        if out_fields['registration_fields']:
            return None, out_fields['registration_fields']

        return {**out_fields['add_fields'], **out_fields['authorise_fields']}, None

    def _collect_fields_and_determine_route(self) -> t.Tuple[int, dict, dict, dict]:
        try:
            if not self.request.channels_permit.is_scheme_available(int(self.request.data['membership_plan'])):
                raise ParseError('membership plan not allowed for this user.')
        except ValueError:
            raise ParseError

        add_fields, auth_fields, enrol_fields = self._collect_credentials_answers(self.request.data)
        scheme_id = self.request.data['membership_plan']
        return scheme_id, auth_fields, enrol_fields, add_fields

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

    def _handle_create_link_route(self, user: CustomUser, scheme_id: int, auth_fields: dict, add_fields: dict,
                                  use_pk: int = None) -> t.Tuple[SchemeAccount, int]:

        data = {'scheme': scheme_id, 'order': 0, **add_fields}
        serializer = self.get_validated_data(data, user)
        scheme_account, _, account_created = self.create_account_with_valid_data(serializer, user, use_pk)
        return_status = status.HTTP_201_CREATED if account_created else status.HTTP_200_OK

        if auth_fields:
            if auth_fields.get('password'):
                # Fix for Barclays sending escaped unicode sequences for special chars.
                auth_fields['password'] = escaped_unicode_pattern.sub(
                    replace_escaped_unicode,
                    auth_fields['password']
                )

            if account_created:
                if scheme_account.scheme.slug in settings.MANUAL_CHECK_SCHEMES:
                    self.prepare_link_for_manual_check(auth_fields, scheme_account)
                    self._manual_check_csv_creation(add_fields)
                else:
                    scheme_account.set_pending()
                    async_link.delay(auth_fields, scheme_account.id, user.id)
            else:
                auth_fields = auth_fields or {}
                self._handle_existing_scheme_account(scheme_account, user, auth_fields)

        return scheme_account, return_status

    @staticmethod
    def _handle_create_join_route(user: CustomUser, channels_permit: Permit,
                                  scheme_id: int, enrol_fields: dict) -> t.Tuple[SchemeAccount, int]:
        try:
            scheme_account = SchemeAccount.objects.get(
                user_set__id=user.id,
                scheme_id=scheme_id,
                status__in=SchemeAccount.JOIN_ACTION_REQUIRED
            )
            scheme_account.set_async_join_status()
        except SchemeAccount.DoesNotExist:
            scheme_account = SchemeAccount.objects.create(
                order=0,
                scheme_id=scheme_id,
                status=SchemeAccount.JOIN_ASYNC_IN_PROGRESS
            )
            SchemeAccountEntry.objects.get_or_create(user=user, scheme_account=scheme_account)

        async_join.delay(scheme_account.id, user.id, channels_permit, scheme_id, enrol_fields)
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

    def _collect_credentials_answers(self, data: dict) -> t.Tuple[t.Optional[dict], t.Optional[dict], t.Optional[dict]]:
        try:
            scheme = get_object_or_404(Scheme, id=data['membership_plan'])
            label_to_type = scheme.get_question_type_dict()
            fields = {}

            for field_name in self.create_update_fields:
                fields[field_name] = self._extract_consent_data(scheme, field_name, data)
                fields[field_name].update(self._collect_field_content(field_name, data, label_to_type))

        except KeyError:
            raise ParseError()

        if fields['enrol_fields']:
            return None, None, fields['enrol_fields']

        if not fields['add_fields'] and scheme.authorisation_required:
            manual_question = scheme.questions.get(manual_question=True).type
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

        client_app = self.request.user.client
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
    authentication_classes = (PropertyAuthentication,)
    override_serializer_classes = {
        'GET': MembershipCardSerializer,
        'POST': LinkMembershipCardSerializer
    }

    @censor_and_decorate
    def list(self, request, *args, **kwargs):
        accounts = self.filter_queryset(self.get_queryset())
        return Response(self.get_serializer(accounts, many=True).data)

    @censor_and_decorate
    def create(self, request, *args, **kwargs):
        scheme_id, auth_fields, enrol_fields, add_fields = self._collect_fields_and_determine_route()
        if enrol_fields:
            account, status_code = self._handle_create_join_route(request.user, request.channels_permit,
                                                                  scheme_id, enrol_fields)
        else:
            account, status_code = self._handle_create_link_route(request.user, scheme_id, auth_fields,
                                                                  add_fields)

        if request.query_params.get('autoLink') == 'True':
            self.auto_link_to_payment_cards(request.user, account)

        return Response(MembershipCardSerializer(account, context={'request': request}).data, status=status_code)


class CardLinkView(ModelViewSet):
    authentication_classes = (PropertyAuthentication,)

    @censor_and_decorate
    def update_payment(self, request, *args, **kwargs):
        self.serializer_class = PaymentCardSerializer
        link, status_code = self._update_link(request.user.id, kwargs['pcard_id'], kwargs['mcard_id'])
        serializer = self.get_serializer(link.payment_card_account)
        return Response(serializer.data, status_code)

    @censor_and_decorate
    def update_membership(self, request, *args, **kwargs):
        self.serializer_class = MembershipCardSerializer
        link, status_code = self._update_link(request.user.id, kwargs['pcard_id'], kwargs['mcard_id'])
        serializer = self.get_serializer(link.scheme_account)
        return Response(serializer.data, status_code)

    @censor_and_decorate
    def destroy_payment(self, request, *args, **kwargs):
        pcard, _ = self._destroy_link(request.user.id, kwargs['pcard_id'], kwargs['mcard_id'])
        return Response({}, status.HTTP_200_OK)

    @censor_and_decorate
    def destroy_membership(self, request, *args, **kwargs):
        _, mcard = self._destroy_link(request.user.id, kwargs['pcard_id'], kwargs['mcard_id'])
        return Response({}, status.HTTP_200_OK)

    def _destroy_link(self, user_id: int, pcard_id: int, mcard_id: int) -> t.Tuple[PaymentCardAccount, SchemeAccount]:
        pcard, mcard = self._collect_cards(pcard_id, mcard_id, user_id)

        try:
            link = PaymentCardSchemeEntry.objects.get(scheme_account=mcard, payment_card_account=pcard)
        except PaymentCardSchemeEntry.DoesNotExist:
            raise NotFound('The link that you are trying to delete does not exist.')

        link.delete()
        return pcard, mcard

    def _update_link(self, user_id: int, pcard_id: int, mcard_id: int) -> t.Tuple[PaymentCardSchemeEntry, int]:
        pcard, mcard = self._collect_cards(pcard_id, mcard_id, user_id)
        status_code = status.HTTP_200_OK
        link, created = PaymentCardSchemeEntry.objects.get_or_create(scheme_account=mcard, payment_card_account=pcard)
        if created:
            status_code = status.HTTP_201_CREATED

        link.activate_link()
        audit.write_to_db(link)
        return link, status_code

    @staticmethod
    def _collect_cards(payment_card_id: int, membership_card_id: int,
                       user_id: int) -> t.Tuple[PaymentCardAccount, SchemeAccount]:
        try:
            payment_card = PaymentCardAccount.objects.get(user_set__id=user_id, pk=payment_card_id)
            membership_card = SchemeAccount.objects.get(user_set__id=user_id, pk=membership_card_id)
        except PaymentCardAccount.DoesNotExist:
            raise NotFound('The payment card of id {} was not found.'.format(payment_card_id))
        except SchemeAccount.DoesNotExist:
            raise NotFound('The membership card of id {} was not found.'.format(membership_card_id))
        except KeyError:
            raise ParseError

        return payment_card, membership_card


class CompositeMembershipCardView(ListMembershipCardView):
    authentication_classes = (PropertyAuthentication,)

    def get_queryset(self):
        query = {
            'user_set__id': self.request.user.id,
            'is_deleted': False,
            'payment_card_account_set__id': self.kwargs['pcard_id']
        }

        return self.request.channels_permit.scheme_account_query(SchemeAccount.objects.filter(**query))

    @censor_and_decorate
    def list(self, request, *args, **kwargs):
        accounts = self.filter_queryset(self.get_queryset())
        return Response(self.get_serializer(accounts, many=True).data)

    @censor_and_decorate
    def create(self, request, *args, **kwargs):
        pcard = get_object_or_404(PaymentCardAccount, pk=kwargs['pcard_id'])
        scheme_id, auth_fields, enrol_fields, add_fields = self._collect_fields_and_determine_route()
        if enrol_fields:
            account, status_code = self._handle_create_join_route(request.user, request.channels_permit,
                                                                  scheme_id, enrol_fields)
        else:
            account, status_code = self._handle_create_link_route(request.user, scheme_id, auth_fields,
                                                                  add_fields)
        PaymentCardSchemeEntry.objects.get_or_create(payment_card_account=pcard, scheme_account=account)
        return Response(MembershipCardSerializer(account, context={'request': request}).data, status=status_code)


class CompositePaymentCardView(ListCreatePaymentCardAccount, PaymentCardCreationMixin, ModelViewSet):
    authentication_classes = (PropertyAuthentication,)
    serializer_class = PaymentCardSerializer

    def get_queryset(self):
        query = {
            'user_set__id': self.request.user.pk,
            'scheme_account_set__id': self.kwargs['mcard_id'],
            'is_deleted': False
        }

        return self.request.channels_permit.scheme_payment_account_query(PaymentCardAccount.objects.filter(**query))

    @censor_and_decorate
    def create(self, request, *args, **kwargs):
        try:
            pcard_data = PaymentCardTranslationSerializer(request.data['card']).data
            if request.allowed_issuers and int(pcard_data['issuer']) not in request.allowed_issuers:
                raise ParseError('issuer not allowed for this user.')

            consent = request.data['account']['consents']
        except (KeyError, ValueError):
            raise ParseError

        exists, pcard, status_code = self.payment_card_already_exists(pcard_data, request.user)
        if exists:
            return Response(self.get_serializer(pcard).data, status=status_code)

        mcard = get_object_or_404(SchemeAccount, pk=kwargs['mcard_id'])
        message, status_code, pcard = self.create_payment_card_account(pcard_data, request.user)
        if status_code == status.HTTP_201_CREATED:
            PaymentCardSchemeEntry.objects.get_or_create(payment_card_account=pcard, scheme_account=mcard)
            return Response(self._create_payment_card_consent(consent, pcard), status=status_code)

        return Response(message, status=status_code)


class MembershipPlanView(ModelViewSet):
    authentication_classes = (PropertyAuthentication,)
    serializer_class = MembershipPlanSerializer

    def get_queryset(self):
        return self.request.channels_permit.scheme_query(Scheme.objects)

    @censor_and_decorate
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)


class ListMembershipPlanView(ModelViewSet, IdentifyCardMixin):
    authentication_classes = (PropertyAuthentication,)
    serializer_class = MembershipPlanSerializer

    def get_queryset(self):
        return self.request.channels_permit.scheme_query(Scheme.objects)

    @censor_and_decorate
    def list(self, request, *args, **kwargs):
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
        return Response(self.get_serializer(scheme).data)


class MembershipTransactionView(ModelViewSet, MembershipTransactionsMixin):
    authentication_classes = (PropertyAuthentication,)
    serializer_class = TransactionsSerializer

    @censor_and_decorate
    def retrieve(self, request, *args, **kwargs):
        url = '{}/transactions/{}'.format(settings.HADES_URL, kwargs['transaction_id'])
        headers = {'Authorization': self._get_auth_token(request.user.id), 'Content-Type': 'application/json'}
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200 and resp.json():
            data = resp.json()
            if isinstance(data, list):
                data = data[0]

            if self._account_belongs_to_user(request.user.id, data.get('scheme_account_id')):
                return Response(self.get_serializer(data, many=False).data)

        return Response({})

    @censor_and_decorate
    def list(self, request, *args, **kwargs):
        url = '{}/transactions/user/{}'.format(settings.HADES_URL, request.user.id)
        headers = {'Authorization': self._get_auth_token(request.user.id), 'Content-Type': 'application/json'}
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200 and resp.json():
            data = self._filter_transactions_for_current_user(request.user.id, resp.json())
            if data:
                return Response(self.get_serializer(data, many=True).data)

        return Response([])

    @censor_and_decorate
    def composite(self, request, *args, **kwargs):
        if not self._account_belongs_to_user(request.user.id, kwargs['mcard_id']):
            return Response([])

        response = self.get_transactions_data(request.user.id, kwargs['mcard_id'])
        return Response(response)

    @staticmethod
    def _account_belongs_to_user(user_id: int, mcard_id: int) -> bool:
        return SchemeAccountEntry.objects.filter(user_id=user_id, scheme_account_id=mcard_id).exists()

    @staticmethod
    def _filter_transactions_for_current_user(user_id: int, data: t.List[dict]) -> t.List[dict]:
        current_user_accounts = {
            account['scheme_account_id']
            for account in SchemeAccountEntry.objects.values('scheme_account_id').filter(user_id=user_id).all()
        }
        return [
            tx
            for tx in data
            if tx.get('scheme_account_id') in current_user_accounts
        ]
