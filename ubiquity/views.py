import uuid

import requests
from django.conf import settings
from django.db import transaction
from rest_framework import status
from rest_framework.exceptions import NotFound, ParseError, ValidationError
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

import analytics
from payment_card.models import PaymentCardAccount
from payment_card.views import ListCreatePaymentCardAccount, RetrievePaymentCardAccount
from scheme.mixins import BaseLinkMixin, IdentifyCardMixin, SchemeAccountCreationMixin, UpdateCredentialsMixin
from scheme.models import Scheme, SchemeAccount, SchemeAccountCredentialAnswer, SchemeCredentialQuestion
from scheme.views import RetrieveDeleteAccount
from ubiquity.authentication import PropertyAuthentication, PropertyOrServiceAuthentication
from ubiquity.tasks import async_link
from ubiquity.censor_empty_fields import censor_and_decorate
from ubiquity.influx_audit import audit
from ubiquity.models import PaymentCardAccountEntry, PaymentCardSchemeEntry, SchemeAccountEntry
from ubiquity.serializers import (MembershipCardSerializer, MembershipPlanSerializer, MembershipTransactionsMixin,
                                  PaymentCardConsentSerializer, PaymentCardSerializer, PaymentCardTranslationSerializer,
                                  PaymentCardUpdateSerializer, ServiceConsentSerializer, TransactionsSerializer,
                                  UbiquityCreateSchemeAccountSerializer)
from user.models import CustomUser
from user.serializers import UbiquityRegisterSerializer


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
        return Response("not implemented yet", status.HTTP_403_FORBIDDEN)

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
        try:
            pcard_data = PaymentCardTranslationSerializer(request.data['card']).data
            if request.allowed_issuers and pcard_data['issuer'] not in request.allowed_issuers:
                raise ParseError('issuer not allowed for this user.')

            consent = request.data['account']['consents']
        except KeyError:
            raise ParseError

        exists, pcard, status_code = self.payment_card_already_exists(pcard_data, request.user)
        if exists:
            return Response(self.get_serializer(pcard).data, status=status_code)

        message, status_code, pcard = self.create_payment_card_account(pcard_data, request.user)
        if status_code == status.HTTP_201_CREATED:
            return Response(self._create_payment_card_consent(consent, pcard), status=status_code)

        return Response(self.get_serializer(pcard).data, status=status_code)


class MembershipCardView(RetrieveDeleteAccount, UpdateCredentialsMixin, SchemeAccountCreationMixin, BaseLinkMixin,
                         ModelViewSet):
    authentication_classes = (PropertyAuthentication,)
    override_serializer_classes = {
        'GET': MembershipCardSerializer,
        'PATCH': MembershipCardSerializer,
        'DELETE': MembershipCardSerializer,
        'PUT': UbiquityCreateSchemeAccountSerializer
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

    @censor_and_decorate
    def retrieve(self, request, *args, **kwargs):
        account = self.get_object()
        return Response(self.get_serializer(account).data)

    @censor_and_decorate
    def update(self, request, *args, **kwargs):
        account = self.get_object()
        new_answers = self._collect_updated_answers(request.data, account.scheme)
        manual_question = SchemeCredentialQuestion.objects.filter(scheme=account.scheme, manual_question=True).first()

        if manual_question and manual_question.type in new_answers:
            query = {
                'scheme_account__scheme': account.scheme,
                'scheme_account__is_deleted': False,
                'answer': new_answers[manual_question.type]
            }
            exclude = {
                'scheme_account': account
            }

            if SchemeAccountCredentialAnswer.objects.filter(**query).exclude(**exclude).exists():
                account.status = account.FAILED_UPDATE
                account.save()
                return Response(self.get_serializer(account).data, status=status.HTTP_200_OK)

        self.update_credentials(account, new_answers)
        account.delete_cached_balance()
        account.set_pending()

        return Response(self.get_serializer(account).data, status=status.HTTP_200_OK)

    @censor_and_decorate
    def replace(self, request, *args, **kwargs):
        # The objective of this end point is to replace an membership card with a new one keeping
        # the same id. The idea is to delete the membership account cascading any deletes and then
        # recreate it forcing the same id.  Note: Forcing an id on create is permitted in Django

        original_scheme_account = self.get_object()
        serializer, auth_fields, enrol_fields = self._verify_membership_card_creation(request)
        account_pk = original_scheme_account.pk
        try:
            with transaction.atomic():
                original_scheme_account.delete()
                account, status_code = self._handle_membership_card_creation(request.user, serializer, auth_fields,
                                                                             enrol_fields, account_pk)
        except Exception:
            raise ParseError
        if status_code == status.HTTP_201_CREATED:
            # Remap status here in case we might want something else eg status.HTTP_205_RESET_CONTENT
            status_code = status.HTTP_200_OK
        return Response(MembershipCardSerializer(account, context={'request': request}).data, status=status_code)

    @censor_and_decorate
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_deleted = True
        instance.save()

        analytics.update_scheme_account_attribute(instance, request.user)
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

    def _verify_membership_card_creation(self, request):
        if request.allowed_schemes and request.data['membership_plan'] not in request.allowed_schemes:
            raise ParseError('membership plan not allowed for this user.')

        add_fields, auth_fields, enrol_fields = self._collect_credentials_answers(request.data)
        add_data = {'scheme': request.data['membership_plan'], 'order': 0, **add_fields}
        serializer = self.get_validated_data(add_data, request.user)
        return serializer, auth_fields, enrol_fields

    def _handle_membership_card_creation(self, user, serializer, auth_fields, enrol_fields, use_pk=None):
        if serializer and serializer.validated_data:
            scheme_account, _, account_created = self.create_account_with_valid_data(serializer, user, use_pk)

            if account_created:
                return_status = status.HTTP_201_CREATED
                if auth_fields:
                    scheme_account.set_pending()
                    async_link.delay(auth_fields, scheme_account.id, user.id)

            else:
                return_status = status.HTTP_200_OK

            return scheme_account, return_status

        else:
            # todo implement enrol
            if enrol_fields:
                pass
            raise NotImplementedError

    def _collect_credentials_answers(self, data):
        try:
            scheme = get_object_or_404(Scheme, id=data['membership_plan'])
            label_to_type = scheme.get_question_type_dict()
            fields = {}

            for field_name in self.create_update_fields:
                fields[field_name] = self._collect_field_content(field_name, data['account'], label_to_type)

        except KeyError:
            raise ParseError()

        if not fields['add_fields'] and scheme.authorisation_required:
            manual_question = scheme.questions.get(manual_question=True).type
            try:
                fields['add_fields'].update({manual_question: fields['authorise_fields'].pop(manual_question)})
            except KeyError:
                raise ParseError()

        elif not fields['add_fields']:
            raise ParseError()

        return fields['add_fields'], fields['authorise_fields'], fields['enrol_fields']

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
        'POST': UbiquityCreateSchemeAccountSerializer,
    }

    @censor_and_decorate
    def list(self, request, *args, **kwargs):
        accounts = self.filter_queryset(self.get_queryset())
        return Response(self.get_serializer(accounts, many=True).data)

    @censor_and_decorate
    def create(self, request, *args, **kwargs):
        serializer, auth_fields, enrol_fields = self._verify_membership_card_creation(request)
        account, status_code = self._handle_membership_card_creation(request.user, serializer, auth_fields,
                                                                     enrol_fields)
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
        serializer, auth_fields, enrol_fields = self._verify_membership_card_creation(request)
        account, status_code = self._handle_membership_card_creation(request.user, serializer, auth_fields,
                                                                     enrol_fields)
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
            if request.allowed_issuers and pcard_data['issuer'] not in request.allowed_issuers:
                raise ParseError('issuer not allowed for this user.')

            consent = request.data['account']['consents']
        except KeyError:
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
    queryset = Scheme.objects
    serializer_class = MembershipPlanSerializer

    @censor_and_decorate
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)


class ListMembershipPlanView(ModelViewSet, IdentifyCardMixin):
    authentication_classes = (PropertyAuthentication,)
    queryset = Scheme.objects
    serializer_class = MembershipPlanSerializer

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
