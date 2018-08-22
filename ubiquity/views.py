import uuid

import requests
from django.conf import settings
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound, ParseError
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from payment_card.models import PaymentCardAccount
from payment_card.views import ListCreatePaymentCardAccount, RetrievePaymentCardAccount
from scheme.credentials import credential_types_set
from scheme.models import Scheme, SchemeAccount
from scheme.serializers import (CreateSchemeAccountSerializer, GetSchemeAccountSerializer, LinkSchemeSerializer,
                                ListSchemeAccountSerializer)
from scheme.views import BaseLinkMixin, CreateAccount, RetrieveDeleteAccount
from ubiquity.authentication import PropertyOrJWTAuthentication
from ubiquity.models import PaymentCardSchemeEntry
from ubiquity.serializers import (ListMembershipCardSerializer, MembershipCardSerializer, PaymentCardConsentSerializer,
                                  PaymentCardSchemeEntrySerializer, PaymentCardSerializer, ServiceConsentSerializer,
                                  TransactionsSerializer)
from user.models import CustomUser
from user.serializers import RegisterSerializer


class ServiceView(APIView):
    authentication_classes = (PropertyOrJWTAuthentication,)
    serializer = RegisterSerializer
    model = CustomUser

    # # todo is this secure?
    # def get(self, request):
    #     user_data = {
    #         'client_id': request.bundle.client.pk,
    #         'email': '{}__{}'.format(request.bundle.client.client_id, request.prop_email),
    #         'uid': request.prop_email,
    #     }
    #     user = get_object_or_404(self.model, **user_data)
    #     return Response({'email': user_data['email'], 'reset_token': user.generate_reset_token()})

    def post(self, request):
        new_user_data = {
            'client_id': request.bundle.client.pk,
            'email': '{}__{}'.format(request.bundle.bundle_id, request.prop_email),
            'uid': request.prop_email,
            'password': str(uuid.uuid4()).lower().replace('-', 'A&')
        }

        new_user = self.serializer(data=new_user_data)
        new_user.is_valid(raise_exception=True)
        user = new_user.save()

        new_consent = ServiceConsentSerializer(data={'user': user.pk, **{k: v for k, v in request.data.items()}})
        try:
            new_consent.is_valid(raise_exception=True)
            new_consent.save()
        except serializers.ValidationError as e:
            user.delete()
            raise e

        return Response(new_user.data)

    # @staticmethod
    # def delete(request):
    #     user = request.user
    # errors     consent = user.serviceconsent
    #     consent.delete()
    #     user.delete()
    #     return Response(status=status.HTTP_204_NO_CONTENT)


class TestBalance(APIView):
    @staticmethod
    def get(request):
        try:
            sa = SchemeAccount.objects.get(id=request.query_params['scheme_account'])
        except KeyError:
            raise ParseError('query parameter scheme_account not found.')
        except SchemeAccount.DoesNotExist:
            raise NotFound('Scheme Account {} not found'.format(request.query_params['scheme_account']))

        return Response(sa.get_cached_balance())


class PaymentCardView(RetrievePaymentCardAccount):
    serializer_class = PaymentCardSerializer

    def get_queryset(self):
        query = {'user_set__id': self.request.user.id}
        if self.request.allowed_issuers:
            query['issuer__in'] = self.request.allowed_issuers

        return self.queryset.filter(**query)


class ListPaymentCardView(ListCreatePaymentCardAccount):
    serializer_class = PaymentCardSerializer

    def get(self, request):
        query = {'user_set__id': request.user.id}
        if request.allowed_issuers:
            query['issuer__in'] = request.allowed_issuers

        accounts = [self.serializer_class(instance=account).data for account in
                    PaymentCardAccount.objects.filter(**query)]
        return Response(accounts, status=200)

    def post(self, request, *args, **kwargs):
        try:
            pcard_data = request.data['card']
            if request.allowed_issuers and pcard_data['issuer'] not in request.allowed_issuers:
                raise ParseError('issuer not allowed for this user.')

            consent = request.data['account']['consent']
        except KeyError:
            raise ParseError

        message, status_code, pcard = self.create_payment_card_account(pcard_data, request.user)
        if status_code == status.HTTP_201_CREATED:
            self._link_to_all_membership_cards(pcard, request.user)
            return Response(self._create_payment_card_consent(consent, pcard), status=status_code)

        return Response(message, status=status_code)

    @staticmethod
    def _create_payment_card_consent(consent_data, pcard):
        serializer = PaymentCardConsentSerializer(data=consent_data)
        serializer.is_valid(raise_exception=True)
        pcard.consent = serializer.validated_data
        pcard.save()
        return PaymentCardSerializer(pcard).data

    @staticmethod
    def _link_to_all_membership_cards(pcard, user):
        for mcard in user.scheme_account_set.all():
            other_entry = PaymentCardSchemeEntry.objects.filter(scheme_account=mcard).first()
            entry, _ = PaymentCardSchemeEntry.objects.get_or_create(payment_card_account=pcard, scheme_account=mcard)

            if other_entry:
                entry.active_link = other_entry.active_link
                entry.save()
            else:
                entry.activate_link()


class MembershipCardView(RetrieveDeleteAccount):
    override_serializer_classes = {
        'GET': MembershipCardSerializer,
        'DELETE': GetSchemeAccountSerializer,
        'OPTIONS': GetSchemeAccountSerializer,
    }

    def get_queryset(self):
        query = {'user_set__id': self.request.user.id}
        if self.request.allowed_schemes:
            query['scheme__in'] = self.request.allowed_schemes

        return SchemeAccount.objects.filter(**query)

    def get(self, request, *args, **kwargs):
        serializer = self.get_serializer_class()
        account = get_object_or_404(self.get_queryset(), pk=kwargs['pk'])
        account.get_cached_balance()
        return Response(serializer(account).data)


class LinkMembershipCardView(CreateAccount, BaseLinkMixin):
    override_serializer_classes = {
        'GET': ListMembershipCardSerializer,
        'POST': CreateSchemeAccountSerializer,
        'OPTIONS': ListSchemeAccountSerializer,
    }

    def get_queryset(self):
        query = {'user_set__id': self.request.user.id}
        if self.request.allowed_schemes:
            query['scheme__in'] = self.request.allowed_schemes

        return SchemeAccount.objects.filter(**query)

    def get(self, request, *args, **kwargs):
        serializer = self.get_serializer_class()
        accounts = self.get_queryset()

        for account in accounts:
            account.get_cached_balance()

        return Response(serializer(accounts, many=True).data)

    def post(self, request, *args, **kwargs):
        if request.allowed_schemes and request.data['scheme'] not in request.allowed_schemes:
            raise ParseError('scheme not allowed for this user.')

        activate = self._collect_credentials_answers(request.data)
        create = {k: v for k, v in request.data.items() if k not in activate.keys()}

        data = self.create_account(create, request.user)
        scheme_account = SchemeAccount.objects.get(id=data['id'])
        serializer = LinkSchemeSerializer(data=activate, context={'scheme_account': scheme_account})
        try:
            balance = self.link_account(serializer, scheme_account, request.user)
        except:
            balance = {}
        scheme_account.link_date = timezone.now()
        scheme_account.save()
        self._link_to_all_payment_cards(scheme_account, request.user)
        return Response(balance, status=status.HTTP_201_CREATED)

    def _collect_credentials_answers(self, data):
        scheme = Scheme.objects.get(id=data['scheme'])
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
        for pcard in user.payment_card_account_set.all():
            other_entry = PaymentCardSchemeEntry.objects.filter(payment_card_account=pcard).first()
            entry, _ = PaymentCardSchemeEntry.objects.get_or_create(payment_card_account=pcard, scheme_account=mcard)

            if other_entry:
                entry.active_link = other_entry.active_link
                entry.save()
            else:
                entry.activate_link()


class LinkUnlinkView(APIView):

    def patch(self, request):
        pcard, mcard = self._collect_cards(request.query_params, request.user.id)

        link, _ = PaymentCardSchemeEntry.objects.get_or_create(scheme_account=mcard, payment_card_account=pcard)
        link.activate_link()

        response = PaymentCardSchemeEntrySerializer(link).data
        return Response(response, status.HTTP_201_CREATED)

    def delete(self, request):
        pcard, mcard = self._collect_cards(request.query_params, request.user.id)

        try:
            link = PaymentCardSchemeEntry.objects.get(scheme_account=mcard, payment_card_account=pcard)
        except PaymentCardSchemeEntry.DoesNotExist:
            raise NotFound('The link that you are trying to delete does not exist.')

        link.delete()
        return Response(status=status.HTTP_202_ACCEPTED)

    @staticmethod
    def _collect_cards(params, user_id):
        try:
            pcard = PaymentCardAccount.objects.get(user_set__id=user_id, pk=params['payment_card'])
            mcard = SchemeAccount.objects.get(user_set__id=user_id, pk=params['membership_card'])
        except PaymentCardAccount.DoesNotExist:
            raise NotFound('The payment card of id {} was not found.'.format(params['payment_card']))
        except SchemeAccount.DoesNotExist:
            raise NotFound('The membership card of id {} was not found.'.format(params['membership_card']))
        except KeyError:
            raise ParseError

        return pcard, mcard


class MembershipCardTransactionsView(APIView):
    serializer = TransactionsSerializer

    def get(self, request, mcard_id):
        url = '{}/transactions/scheme_account/{}'.format(settings.HADES_URL, mcard_id)
        headers = {'Authorization': request.META['HTTP_AUTHORIZATION'], 'Content-Type': 'application/json'}
        resp = requests.get(url, headers=headers)
        serializer = self.serializer(resp.json(), many=True)
        return Response(serializer.data)


class UserTransactions(APIView):
    serializer = TransactionsSerializer

    def get(self, request):
        headers = {'Authorization': request.META['HTTP_AUTHORIZATION'], 'Content-Type': 'application/json'}
        url = settings.HADES_URL + '/transactions/scheme_account/{}'
        transactions = []
        for account in SchemeAccount.objects.filter(user_set__id=request.user.id).all():
            resp = requests.get(url.format(account.pk), headers=headers)
            transactions.extend(resp.json())

        serializer = self.serializer(transactions, many=True)
        return Response(serializer.data)
