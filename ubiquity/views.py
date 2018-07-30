import uuid

import requests
from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import NotFound, ParseError, ValidationError
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from payment_card.models import PaymentCardAccount
from payment_card.views import ListCreatePaymentCardAccount, RetrievePaymentCardAccount
from scheme.credentials import credential_types_set
from scheme.models import Scheme, SchemeAccount
from scheme.serializers import (CreateSchemeAccountSerializer, GetSchemeAccountSerializer, LinkSchemeSerializer,
                                ListSchemeAccountSerializer)
from scheme.views import BaseLinkMixin, RetrieveDeleteAccount, SchemeAccountCreationMixin
from ubiquity.authentication import PropertyAuthentication, PropertyOrServiceAuthentication
from ubiquity.influx_audit import audit
from ubiquity.models import PaymentCardSchemeEntry
from ubiquity.serializers import (ListMembershipCardSerializer, MembershipCardSerializer, PaymentCardConsentSerializer,
                                  PaymentCardSerializer, ServiceConsentSerializer,
                                  TransactionsSerializer)
from user.models import CustomUser
from user.serializers import RegisterSerializer


class PaymentCardConsentMixin:
    @staticmethod
    def _create_payment_card_consent(consent_data, pcard):
        serializer = PaymentCardConsentSerializer(data=consent_data)
        serializer.is_valid(raise_exception=True)
        pcard.consent = serializer.validated_data
        pcard.save()
        return PaymentCardSerializer(pcard).data


class ServiceView(ModelViewSet):
    authentication_classes = (PropertyOrServiceAuthentication,)
    serializer_class = ServiceConsentSerializer

    def retrieve(self, request, *args, **kwargs):
        if not request.user.is_active:
            raise NotFound

        return Response(self.get_serializer(request.user.serviceconsent).data)

    def create(self, request, *args, **kwargs):
        new_user_data = {
            'client_id': request.bundle.client.pk,
            'email': '{}__{}'.format(request.bundle.bundle_id, request.prop_email),
            'uid': request.prop_email,
            'password': str(uuid.uuid4()).lower().replace('-', 'A&')
        }

        try:
            user = CustomUser.objects.get(email=new_user_data['email'])
        except CustomUser.DoesNotExist:
            status_code = 201
            new_user = RegisterSerializer(data=new_user_data)
            new_user.is_valid(raise_exception=True)
            user = new_user.save()
        else:
            if not user.is_active:
                status_code = 201
                user.is_active = True
                user.save()
            else:
                status_code = 200
        finally:
            if hasattr(user, 'serviceconsent'):
                user.serviceconsent.delete()

            consent = self.get_serializer(
                data={'user': user.pk, **{k: v for k, v in request.data['consent'].items()}})
            try:
                consent.is_valid(raise_exception=True)
                consent.save()
            except ValidationError:
                user.is_active = False
                user.save()
                raise ParseError

        return Response(consent.data, status=status_code)

    def destroy(self, request, *args, **kwargs):
        response = self.get_serializer(request.user.serviceconsent).data
        request.user.serviceconsent.delete()
        request.user.is_active = False
        request.user.save()
        return Response(response)


class PaymentCardView(RetrievePaymentCardAccount, ModelViewSet):
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

    def destroy(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)


class ListPaymentCardView(ListCreatePaymentCardAccount, PaymentCardConsentMixin, ModelViewSet):
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

    def list(self, request, *args, **kwargs):
        accounts = self.filter_queryset(self.get_queryset())
        return Response(self.get_serializer(accounts, many=True).data, status=200)

    def create(self, request, *args, **kwargs):
        try:
            pcard_data = request.data['card']
            if request.allowed_issuers and pcard_data['issuer'] not in request.allowed_issuers:
                raise ParseError('issuer not allowed for this user.')

            consent = request.data['account']['consents'][0]
        except KeyError:
            raise ParseError

        message, status_code, pcard = self.create_payment_card_account(pcard_data, request.user)
        if status_code == status.HTTP_201_CREATED:
            self._link_to_all_membership_cards(pcard, request.user)
            return Response(self._create_payment_card_consent(consent, pcard), status=status_code)

        return Response(message, status=status_code)

    @staticmethod
    def _link_to_all_membership_cards(pcard, user):
        updated_entries = []
        for mcard in user.scheme_account_set.all():
            other_entry = PaymentCardSchemeEntry.objects.filter(scheme_account=mcard).first()
            entry, _ = PaymentCardSchemeEntry.objects.get_or_create(payment_card_account=pcard, scheme_account=mcard)

            if other_entry:
                entry.active_link = other_entry.active_link
                entry.save()
            else:
                entry.activate_link()

            updated_entries.append(entry)

        audit.write_to_db(updated_entries, many=True)


class MembershipCardView(RetrieveDeleteAccount, ModelViewSet):
    authentication_classes = (PropertyAuthentication,)
    serializer_class = MembershipCardSerializer
    override_serializer_classes = {
        'GET': MembershipCardSerializer,
        'DELETE': GetSchemeAccountSerializer,
        'OPTIONS': GetSchemeAccountSerializer,
    }

    def get_queryset(self):
        query = {
            'user_set__id': self.request.user.id,
            'is_deleted': False
        }
        if self.request.allowed_schemes:
            query['scheme__in'] = self.request.allowed_schemes

        return SchemeAccount.objects.filter(**query)

    def retrieve(self, request, *args, **kwargs):
        account = self.get_object()
        account.get_cached_balance()
        return Response(self.get_serializer(account).data)

    def destroy(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)

    def transactions(self, request, mcard_id):
        self.get_serializer_class = lambda: TransactionsSerializer
        url = '{}/transactions/scheme_account/{}'.format(settings.HADES_URL, mcard_id)
        headers = {'Authorization': request.META['HTTP_AUTHORIZATION'], 'Content-Type': 'application/json'}
        resp = requests.get(url, headers=headers)
        result = resp.json() if resp.status_code == 200 else []
        return Response(self.get_serializer(result, many=True).data)


class ListMembershipCardView(SchemeAccountCreationMixin, BaseLinkMixin, ModelViewSet):
    authentication_classes = (PropertyAuthentication,)
    serializer_class = ListMembershipCardSerializer
    override_serializer_classes = {
        'GET': ListMembershipCardSerializer,
        'POST': CreateSchemeAccountSerializer,
        'OPTIONS': ListSchemeAccountSerializer,
    }

    def get_queryset(self):
        query = {
            'user_set__id': self.request.user.id,
            'is_deleted': False
        }
        if self.request.allowed_schemes:
            query['scheme__in'] = self.request.allowed_schemes

        return SchemeAccount.objects.filter(**query)

    def list(self, request, *args, **kwargs):
        accounts = self.filter_queryset(self.get_queryset())

        for account in accounts:
            account.get_cached_balance()

        return Response(self.get_serializer(accounts, many=True).data)

    def create(self, request, *args, **kwargs):
        account, status_code = self._handle_membership_card_creation(request)
        self._link_to_all_payment_cards(account, request.user)
        return Response(MembershipCardSerializer(account).data, status=status_code)

    def _handle_membership_card_creation(self, request):
        if request.allowed_schemes and request.data['membership_plan'] not in request.allowed_schemes:
            raise ParseError('membership plan not allowed for this user.')

        activate = self._collect_credentials_answers(request.data)
        create = {
            k if k != 'membership_plan' else 'scheme': v
            for k, v in request.data.items()
            if k not in activate.keys()
        }

        data = self.create_account(create, request.user)
        scheme_account = SchemeAccount.objects.get(id=data['id'])
        serializer = LinkSchemeSerializer(data=activate, context={'scheme_account': scheme_account})

        self.link_account(serializer, scheme_account, request.user)

        scheme_account.link_date = timezone.now()
        scheme_account.save()
        return scheme_account, status.HTTP_201_CREATED

    def _collect_credentials_answers(self, data):
        scheme = Scheme.objects.get(id=data['membership_plan'])
        allowed_answers = self.allowed_answers(scheme)
        return {
            k: v
            for k, v in data.items()
            if k in credential_types_set and k not in allowed_answers
        }

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

    @staticmethod
    def _link_to_all_payment_cards(mcard, user):
        updated_entries = []
        for pcard in user.payment_card_account_set.all():
            other_entry = PaymentCardSchemeEntry.objects.filter(payment_card_account=pcard).first()
            entry, _ = PaymentCardSchemeEntry.objects.get_or_create(payment_card_account=pcard, scheme_account=mcard)

            if other_entry:
                entry.active_link = other_entry.active_link
                entry.save()
            else:
                entry.activate_link()

            updated_entries.append(entry)

        audit.write_to_db(updated_entries, many=True)


class CreateDeleteLinkView(ModelViewSet):
    authentication_classes = (PropertyAuthentication,)

    def update_payment(self, request, *args, **kwargs):
        self.serializer_class = PaymentCardSerializer
        link = self._update_link(request, *args, **kwargs)
        serializer = self.get_serializer(link.payment_card_account)
        return Response(serializer.data, status.HTTP_201_CREATED)

    def update_membership(self, request, *args, **kwargs):
        self.serializer_class = MembershipCardSerializer
        link = self._update_link(request, *args, **kwargs)
        serializer = self.get_serializer(link.scheme_account)
        return Response(serializer.data, status.HTTP_201_CREATED)

    def destroy_payment(self, request, *args, **kwargs):
        self.serializer_class = PaymentCardSerializer
        pcard, _ = self._destroy_link(request, *args, **kwargs)
        serializer = self.get_serializer(pcard)
        return Response(serializer.data, status.HTTP_201_CREATED)

    def destroy_membership(self, request, *args, **kwargs):
        self.serializer_class = MembershipCardSerializer
        _, mcard = self._destroy_link(request, *args, **kwargs)
        serializer = self.get_serializer(mcard)
        return Response(serializer.data, status.HTTP_201_CREATED)

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

        link, _ = PaymentCardSchemeEntry.objects.get_or_create(scheme_account=mcard, payment_card_account=pcard)
        link.activate_link()
        audit.write_to_db(link)
        return link

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


class UserTransactions(ModelViewSet):
    authentication_classes = (PropertyAuthentication,)
    serializer_class = TransactionsSerializer

    def get_queryset(self):
        return SchemeAccount.objects.filter(user_set__id=self.request.user.id).all()

    def list(self, request, *args, **kwargs):
        headers = {'Authorization': request.META['HTTP_AUTHORIZATION'], 'Content-Type': 'application/json'}
        url = settings.HADES_URL + '/transactions/scheme_account/{}'
        transactions = []
        for account in self.get_queryset():
            resp = requests.get(url.format(account.pk), headers=headers)
            if resp.status_code == 200:
                transactions.extend(resp.json())

        serializer = self.get_serializer(transactions, many=True)
        return Response(serializer.data)


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

    def list(self, request, *args, **kwargs):
        accounts = self.filter_queryset(self.get_queryset())
        for account in accounts:
            account.get_cached_balance()

        return Response(self.get_serializer(accounts, many=True).data)

    def create(self, request, *args, **kwargs):
        pcard = get_object_or_404(PaymentCardAccount, pk=kwargs['pcard_id'])
        account, status_code = self._handle_membership_card_creation(request)
        PaymentCardSchemeEntry.objects.get_or_create(payment_card_account=pcard, scheme_account=account)
        return Response(MembershipCardSerializer(account).data, status=status_code)


class CompositePaymentCardView(ListCreatePaymentCardAccount, PaymentCardConsentMixin, ModelViewSet):
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

    def create(self, request, *args, **kwargs):
        try:
            pcard_data = request.data['card']
            if request.allowed_issuers and pcard_data['issuer'] not in request.allowed_issuers:
                raise ParseError('issuer not allowed for this user.')

            consent = request.data['consent']
        except KeyError:
            raise ParseError

        mcard = get_object_or_404(SchemeAccount, pk=kwargs['mcard_id'])
        message, status_code, pcard = self.create_payment_card_account(pcard_data, request.user)
        if status_code == status.HTTP_201_CREATED:
            PaymentCardSchemeEntry.objects.get_or_create(payment_card_account=pcard, scheme_account=mcard)
            return Response(self._create_payment_card_consent(consent, pcard), status=status_code)

        return Response(message, status=status_code)
