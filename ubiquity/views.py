import re
import uuid
from pathlib import Path

import arrow
from azure.storage.blob import BlockBlobService
from django.conf import settings
from raven.contrib.django.raven_compat.models import client as sentry
from requests import request
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound, ParseError, ValidationError
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

import analytics
from hermes import settings as project_settings
from hermes.traced_requests import requests
from payment_card.models import PaymentCardAccount
from payment_card.views import ListCreatePaymentCardAccount, RetrievePaymentCardAccount
from scheme.mixins import (BaseLinkMixin, IdentifyCardMixin, SchemeAccountCreationMixin, UpdateCredentialsMixin,
                           SchemeAccountJoinMixin)
from scheme.models import Scheme, SchemeAccount, SchemeCredentialQuestion
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
from ubiquity.tasks import async_link
from user.models import CustomUser
from user.serializers import UbiquityRegisterSerializer

escaped_unicode_pattern = re.compile(r'\\(\\u[a-fA-F0-9]{4})')


def replace_escaped_unicode(match):
    return match.group(1).encode().decode('unicode-escape')


class PaymentCardCreationMixin:
    @staticmethod
    def _create_payment_card_consent(consent_data, pcard):
        serializer = PaymentCardConsentSerializer(data=consent_data, many=True)
        serializer.is_valid(raise_exception=True)
        pcard.consents = serializer.validated_data
        pcard.save()
        return PaymentCardSerializer(pcard).data

    @staticmethod
    def _update_payment_card_consent(consent_data, pcard_pk):
        if not consent_data:
            consents = []
        else:
            serializer = PaymentCardConsentSerializer(data=consent_data, many=True)
            serializer.is_valid(raise_exception=True)
            consents = serializer.validated_data

        PaymentCardAccount.objects.filter(pk=pcard_pk).update(consents=consents)

    def payment_card_already_exists(self, data, user):
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
    def _link_account_to_new_user(account, user):
        if account.is_deleted:
            account.is_deleted = False
            account.save()

        PaymentCardAccountEntry.objects.get_or_create(user=user, payment_card_account=account)
        for scheme_account in account.scheme_account_set.all():
            SchemeAccountEntry.objects.get_or_create(user=user, scheme_account=scheme_account)

    @staticmethod
    def _collect_creation_data(request):
        """
        :type request: ModelViewSet.request
        :rtype: (dict, dict)
        """
        try:
            pcard_data = PaymentCardTranslationSerializer(request.data['card']).data
            if request.allowed_issuers and int(pcard_data['issuer']) not in request.allowed_issuers:
                raise ParseError('issuer not allowed for this user.')

            consent = request.data['account']['consents']
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

        return Response(self.get_serializer(request.user.serviceconsent).data)

    @censor_and_decorate
    def create(self, request, *args, **kwargs):
        status_code = 200
        consent_data = request.data['consent']
        if 'email' not in consent_data:
            raise ParseError

        new_user_data = {
            'client_id': request.bundle.client.pk,
            'bundle_id': request.bundle.bundle_id,
            'email': consent_data['email'],
            'external_id': request.prop_id,
            'password': str(uuid.uuid4()).lower().replace('-', 'A&')
        }

        try:
            user = CustomUser.objects.get(client=request.bundle.client, external_id=request.prop_id)
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
            sentry.captureException()
        return Response(response)

    def _add_consent(self, user, consent_data):
        try:
            consent = self.get_serializer(data={'user': user.pk, **consent_data})
            consent.is_valid(raise_exception=True)
            consent.save()
        except ValidationError:
            user.is_active = False
            user.save()
            raise ParseError

        return consent


def send_data_to_atlas(response):
    url = f"{project_settings.ATLAS_URL}/ubiquity_user/save"
    data = {
        'email': response['consent']['email'],
        'opt_out_timestamp': arrow.get(response['consent']['timestamp']).format("YYYY-MM-DD hh:mm:ss")
    }
    request("POST", url=url, headers=request_header(), json=data)


def request_header():
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Token {}'.format(project_settings.SERVICE_API_KEY)
    }
    return headers


class PaymentCardView(RetrievePaymentCardAccount, PaymentCardCreationMixin, ModelViewSet):
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
        pcard_data, consent = self._collect_creation_data(request)
        if pcard_data['fingerprint'] != account.fingerprint:
            raise ParseError('cannot override fingerprint.')

        pcard_data['token'] = account.token
        new_card_data = PaymentCardReplaceSerializer(data=pcard_data)
        new_card_data.is_valid(raise_exception=True)
        PaymentCardAccount.objects.filter(pk=account.pk).update(**new_card_data.validated_data)
        # todo should we replace the consent too?

        account.refresh_from_db()
        return Response(self.get_serializer(account).data, status.HTTP_200_OK)

    @censor_and_decorate
    def destroy(self, request, *args, **kwargs):
        super().delete(request, *args, **kwargs)
        return Response({}, status=status.HTTP_200_OK)


class ListPaymentCardView(ListCreatePaymentCardAccount, PaymentCardCreationMixin, ModelViewSet):
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
        pcard_data, consent = self._collect_creation_data(request)
        exists, pcard, status_code = self.payment_card_already_exists(pcard_data, request.user)
        if exists:
            return Response(self.get_serializer(pcard).data, status=status_code)

        message, status_code, pcard = self.create_payment_card_account(pcard_data, request.user)
        if status_code == status.HTTP_201_CREATED:
            return Response(self._create_payment_card_consent(consent, pcard), status=status_code)

        return Response(self.get_serializer(pcard).data, status=status_code)


class MembershipCardView(RetrieveDeleteAccount, UpdateCredentialsMixin, SchemeAccountCreationMixin, BaseLinkMixin,
                         SchemeAccountJoinMixin, ModelViewSet):
    authentication_classes = (PropertyAuthentication,)
    override_serializer_classes = {
        'GET': MembershipCardSerializer,
        'PATCH': MembershipCardSerializer,
        'DELETE': MembershipCardSerializer,
        'PUT': LinkMembershipCardSerializer
    }
    create_update_fields = ('add_fields', 'authorise_fields', 'enrol_fields')

    def get_queryset(self):
        query = {
            'user_set__id': self.request.user.id,
            'is_deleted': False
        }
        if self.request.allowed_schemes:
            query['scheme__in'] = self.request.allowed_schemes

        return SchemeAccount.objects.filter(**query)

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

    @censor_and_decorate
    def update(self, request, *args, **kwargs):
        account = self.get_object()
        new_answers = self._collect_updated_answers(request.data, account.scheme)
        manual_question = SchemeCredentialQuestion.objects.filter(scheme=account.scheme, manual_question=True).first()

        if new_answers.get('password'):
            # Fix for Barclays sending escaped unicode sequences for special chars.
            new_answers['password'] = escaped_unicode_pattern.sub(replace_escaped_unicode, new_answers['password'])

        if manual_question and manual_question.type in new_answers:
            if self.card_with_same_data_already_exists(account, account.scheme, new_answers[manual_question.type]):
                account.status = account.FAILED_UPDATE
                account.save()
                return Response(self.get_serializer(account).data, status=status.HTTP_200_OK)

        self.update_credentials(account, new_answers)
        account.delete_cached_balance()
        account.set_pending()

        return Response(self.get_serializer(account).data, status=status.HTTP_200_OK)

    @censor_and_decorate
    def replace(self, request, *args, **kwargs):
        account = self.get_object()
        scheme_id, auth_fields, enrol_fields, add_fields = self._collect_fields_and_determine_route()
        if request.allowed_schemes and scheme_id not in request.allowed_schemes:
            raise ParseError('membership plan not allowed for this user.')

        if enrol_fields:
            raise NotImplemented
        else:
            new_answers, main_answer = self._get_new_answers(add_fields, auth_fields)

            if self.card_with_same_data_already_exists(account, scheme_id, main_answer):
                account.status = account.FAILED_UPDATE
                account.save()
            else:
                self.replace_credentials_and_scheme(account, new_answers, scheme_id)

        return Response(MembershipCardSerializer(account).data, status=status.HTTP_200_OK)

    @censor_and_decorate
    def destroy(self, request, *args, **kwargs):
        super().delete(request, *args, **kwargs)
        return Response({}, status=status.HTTP_200_OK)

    @staticmethod
    @censor_and_decorate
    def membership_plan(request, mcard_id):
        mcard = get_object_or_404(SchemeAccount, id=mcard_id)
        return Response(MembershipPlanSerializer(mcard.scheme).data)

    @staticmethod
    def _collect_field_content(field, data, label_to_type):
        return {
            label_to_type[item['column']]: item['value']
            for item in data.get(field, [])
        }

    def _collect_updated_answers(self, data, scheme):
        label_to_type = scheme.get_question_type_dict()
        out_fields = {}
        try:
            for field_name in self.create_update_fields:
                out_fields.update(
                    self._collect_field_content(field_name, data['account'], label_to_type)
                )

        except KeyError:
            raise ParseError

        if not out_fields:
            raise ParseError()

        return out_fields

    def _collect_fields_and_determine_route(self):
        """
        :rtype: tuple[int, dict, dict, dict]
        """
        try:
            if self.request.allowed_schemes and int(
                    self.request.data['membership_plan']) not in self.request.allowed_schemes:
                raise ParseError('membership plan not allowed for this user.')
        except ValueError:
            raise ParseError

        add_fields, auth_fields, enrol_fields = self._collect_credentials_answers(self.request.data)
        scheme_id = self.request.data['membership_plan']
        return scheme_id, auth_fields, enrol_fields, add_fields

    @staticmethod
    def _handle_existing_scheme_account(scheme_account, user, auth_fields):
        existing_answers = scheme_account.get_auth_fields()
        for k, v in existing_answers.items():
            if auth_fields.get(k) != v:
                raise ParseError('This card already exists, but the provided credentials do not match.')

        SchemeAccountEntry.objects.get_or_create(user=user, scheme_account=scheme_account)
        for card in scheme_account.payment_card_account_set.all():
            PaymentCardAccountEntry.objects.get_or_create(user=user, payment_card_account=card)

    def _handle_membership_card_link_route(self, user, scheme_id, auth_fields, add_fields, use_pk=None):
        """
        :type user: user.models.CustomUser
        :type scheme_id: int
        :type auth_fields: dict
        :type add_fields: dict
        :type use_pk: int
        :rtype: tuple[SchemeAccount, int]
        """
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

    def _handle_membership_card_join_route(self, user, scheme_id, enrol_fields):
        """
        :type user: user.models.CustomUser
        :type scheme_id: int
        :type enrol_fields: dict
        :rtype: tuple[SchemeAccount, int]
        """

        join_data = {
            'order': 0,
            **enrol_fields,
            'save_user_information': 'false'
        }
        _, status_code, scheme_account = self.handle_join_request(join_data, user, scheme_id)
        return scheme_account, status_code

    @staticmethod
    def _manual_check_csv_creation(add_fields):
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

    def _collect_credentials_answers(self, data):
        try:
            scheme = get_object_or_404(Scheme, id=data['membership_plan'])
            label_to_type = scheme.get_question_type_dict()
            fields = {}

            for field_name in self.create_update_fields:
                fields[field_name] = self._collect_field_content(field_name, data['account'], label_to_type)

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

    @staticmethod
    def allowed_answers(scheme):
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
            account, status_code = self._handle_membership_card_join_route(request.user, scheme_id, enrol_fields)
        else:
            account, status_code = self._handle_membership_card_link_route(request.user, scheme_id, auth_fields,
                                                                           add_fields)

        return Response(MembershipCardSerializer(account, context={'request': request}).data, status=status_code)


class CardLinkView(ModelViewSet):
    authentication_classes = (PropertyAuthentication,)

    @censor_and_decorate
    def update_payment(self, request, *args, **kwargs):
        self.serializer_class = PaymentCardSerializer
        link, status_code = self._update_link(request, *args, **kwargs)
        serializer = self.get_serializer(link.payment_card_account)
        return Response(serializer.data, status_code)

    @censor_and_decorate
    def update_membership(self, request, *args, **kwargs):
        self.serializer_class = MembershipCardSerializer
        link, status_code = self._update_link(request, *args, **kwargs)
        serializer = self.get_serializer(link.scheme_account)
        return Response(serializer.data, status_code)

    @censor_and_decorate
    def destroy_payment(self, request, *args, **kwargs):
        pcard, _ = self._destroy_link(request, *args, **kwargs)
        return Response({}, status.HTTP_200_OK)

    @censor_and_decorate
    def destroy_membership(self, request, *args, **kwargs):
        _, mcard = self._destroy_link(request, *args, **kwargs)
        return Response({}, status.HTTP_200_OK)

    def _destroy_link(self, request, *args, **kwargs):
        pcard, mcard = self._collect_cards(kwargs['pcard_id'], kwargs['mcard_id'], request.user.id)

        try:
            link = PaymentCardSchemeEntry.objects.get(scheme_account=mcard, payment_card_account=pcard)
        except PaymentCardSchemeEntry.DoesNotExist:
            raise NotFound('The link that you are trying to delete does not exist.')

        link.delete()
        return pcard, mcard

    def _update_link(self, request, *args, **kwargs):
        pcard, mcard = self._collect_cards(kwargs['pcard_id'], kwargs['mcard_id'], request.user.id)
        status_code = status.HTTP_200_OK
        link, created = PaymentCardSchemeEntry.objects.get_or_create(scheme_account=mcard, payment_card_account=pcard)
        if created:
            status_code = status.HTTP_201_CREATED

        link.activate_link()
        audit.write_to_db(link)
        return link, status_code

    @staticmethod
    def _collect_cards(payment_card_id, membership_card_id, user_id):
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
        if self.request.allowed_schemes:
            query['scheme__in'] = self.request.allowed_schemes

        return SchemeAccount.objects.filter(**query)

    @censor_and_decorate
    def list(self, request, *args, **kwargs):
        accounts = self.filter_queryset(self.get_queryset())
        return Response(self.get_serializer(accounts, many=True).data)

    @censor_and_decorate
    def create(self, request, *args, **kwargs):
        pcard = get_object_or_404(PaymentCardAccount, pk=kwargs['pcard_id'])
        scheme_id, auth_fields, enrol_fields, add_fields = self._collect_fields_and_determine_route(request)
        if enrol_fields:
            account, status_code = self._handle_membership_card_join_route(request.user, scheme_id, enrol_fields)
        else:
            account, status_code = self._handle_membership_card_link_route(request.user, scheme_id, auth_fields,
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
        if self.request.allowed_schemes:
            query['scheme__in'] = self.request.allowed_schemes

        return PaymentCardAccount.objects.filter(**query)

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
        if self.request.allowed_schemes:
            return Scheme.objects.filter(id__in=self.request.allowed_schemes)
        return Scheme.objects

    @censor_and_decorate
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)


class ListMembershipPlanView(ModelViewSet, IdentifyCardMixin):
    authentication_classes = (PropertyAuthentication,)
    serializer_class = MembershipPlanSerializer

    def get_queryset(self):
        if self.request.allowed_schemes:
            return Scheme.objects.filter(id__in=self.request.allowed_schemes)
        return Scheme.objects

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
        response = self.get_serializer(resp.json()).data if resp.status_code == 200 and resp.json() else {}
        return Response(response)

    @censor_and_decorate
    def list(self, request, *args, **kwargs):
        url = '{}/transactions/user/{}'.format(settings.HADES_URL, request.user.id)
        headers = {'Authorization': self._get_auth_token(request.user.id), 'Content-Type': 'application/json'}
        resp = requests.get(url, headers=headers)
        response = self.get_serializer(resp.json(), many=True).data if resp.status_code == 200 and resp.json() else []
        return Response(response)

    @censor_and_decorate
    def composite(self, request, *args, **kwargs):
        response = self.get_transactions_data(request.user.id, kwargs['mcard_id'])
        return Response(response)
