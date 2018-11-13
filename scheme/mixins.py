import json
import socket
import uuid

from hermes.traced_requests import requests
from django.conf import settings
from django.db import transaction
from raven.contrib.django.raven_compat.models import client as sentry
from requests import RequestException
from rest_framework import serializers, status
from rest_framework.generics import get_object_or_404

import analytics
from scheme.encyption import AESCipher
from scheme.models import ConsentStatus, JourneyTypes, Scheme, SchemeAccount, SchemeAccountCredentialAnswer
from scheme.serializers import (JoinSerializer, MidasUserConsentSerializer, UpdateCredentialSerializer,
                                UserConsentSerializer)
from ubiquity.models import PaymentCardAccountEntry, SchemeAccountEntry


class BaseLinkMixin(object):

    @staticmethod
    def link_account(serializer, scheme_account, user):
        serializer.is_valid(raise_exception=True)
        return BaseLinkMixin._link_account(serializer.validated_data, scheme_account, user)

    @staticmethod
    def _link_account(data, scheme_account, user):
        consent_data = []
        user_consents = []
        midas_consent_data = None

        if 'consents' in data:
            consent_data = data.pop('consents')
            user_consents = UserConsentSerializer.get_user_consents(scheme_account, consent_data, user)
            UserConsentSerializer.validate_consents(user_consents, scheme_account.scheme.id, JourneyTypes.LINK.value)

            user_consent_serializer = MidasUserConsentSerializer(user_consents, many=True)
            midas_consent_data = user_consent_serializer.data

        for answer_type, answer in data.items():
            SchemeAccountCredentialAnswer.objects.update_or_create(
                question=scheme_account.question(answer_type),
                scheme_account=scheme_account, defaults={'answer': answer})

        midas_information = scheme_account.get_cached_balance(user_consents=midas_consent_data)

        response_data = {
            'balance': midas_information,
            'status': scheme_account.status,
            'status_name': scheme_account.status_name
        }
        response_data.update(dict(data))

        if consent_data and scheme_account.status == SchemeAccount.ACTIVE:
            for user_consent in user_consents:
                user_consent.status = ConsentStatus.SUCCESS
                user_consent.save()

        analytics.update_scheme_account_attribute(scheme_account, user)

        return response_data


class SwappableSerializerMixin(object):
    serializer_class = None
    override_serializer_classes = None
    context = None

    def get_serializer_class(self):
        return self.override_serializer_classes[self.request.method]


class IdentifyCardMixin:
    @staticmethod
    def _get_scheme(base_64_image):
        data = {
            'uuid': str(uuid.uuid4()),
            'base64img': base_64_image
        }
        headers = {
            'Content-Type': 'application/json'
        }
        resp = requests.post(settings.HECATE_URL + '/classify', json=data, headers=headers)
        return resp.json()


class SchemeAccountCreationMixin(SwappableSerializerMixin):
    def get_validated_data(self, data, user):
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        # my360 schemes should never come through this endpoint
        scheme = Scheme.objects.get(id=data['scheme'])
        if scheme.url == settings.MY360_SCHEME_URL:
            metadata = {
                'scheme name': scheme.name,
            }
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

    def create_account(self, data, user, user_pk=None):
        serializer = self.get_validated_data(data, user)
        return self.create_account_with_valid_data(serializer, user, user_pk)

    def create_account_with_valid_data(self, serializer, user, user_pk=None):
        account_created = False
        data = serializer.validated_data
        answer_type = serializer.context['answer_type']
        try:
            query = {
                'scheme__id': data['scheme'],
                'schemeaccountcredentialanswer__answer': data[answer_type],
                'is_deleted': False
            }
            scheme_account = SchemeAccount.objects.get(**query)
            SchemeAccountEntry.objects.get_or_create(user=user, scheme_account=scheme_account)
            for card in scheme_account.payment_card_account_set.all():
                PaymentCardAccountEntry.objects.get_or_create(user=user, payment_card_account=card)

        except SchemeAccount.DoesNotExist:
            scheme_account, account_created = self._create_account(user, data, answer_type, user_pk)

        data['id'] = scheme_account.id
        return scheme_account, data, account_created

    @staticmethod
    def _create_account(user, data, answer_type, user_pk=None):
        account_created = False  # Required for /ubiquity

        if type(data) == int:
            return data

        with transaction.atomic():
            try:
                scheme_account = SchemeAccount.objects.get(
                    user_set__id=user.id,
                    scheme_id=data['scheme'],
                    status=SchemeAccount.JOIN,
                    is_deleted=False
                )

                scheme_account.order = data['order']
                scheme_account.status = SchemeAccount.WALLET_ONLY
                scheme_account.save()
            except SchemeAccount.DoesNotExist:
                scheme_account = SchemeAccount(
                    scheme_id=data['scheme'],
                    order=data['order'],
                    status=SchemeAccount.WALLET_ONLY
                )
                if user_pk is not None:
                    scheme_account.pk = user_pk
                scheme_account.save(force_insert=True)

                SchemeAccountEntry.objects.create(scheme_account=scheme_account, user=user)
                account_created = True
            SchemeAccountCredentialAnswer.objects.create(
                scheme_account=scheme_account,
                question=scheme_account.question(answer_type),
                answer=data[answer_type],
            )

            if 'consents' in data:
                user_consents = UserConsentSerializer.get_user_consents(scheme_account, data.pop('consents'), user)
                UserConsentSerializer.validate_consents(user_consents, scheme_account.scheme, JourneyTypes.ADD.value)
                for user_consent in user_consents:
                    user_consent.status = ConsentStatus.SUCCESS
                    user_consent.save()

        analytics.update_scheme_account_attribute(scheme_account, user)

        return scheme_account, account_created


class SchemeAccountJoinMixin:

    def handle_join_request(self, request, *args, **kwargs):
        scheme_id = int(kwargs['pk'])
        join_scheme = get_object_or_404(Scheme.objects, id=scheme_id)
        serializer = JoinSerializer(data=request.data, context={
            'scheme': join_scheme,
            'user': request.user
        })
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        data['scheme'] = scheme_id
        scheme_account = self.create_join_account(data, request.user, scheme_id)

        try:
            if 'consents' in serializer.validated_data:
                consent_data = serializer.validated_data.pop('consents')

                user_consents = UserConsentSerializer.get_user_consents(scheme_account, consent_data, request.user)
                UserConsentSerializer.validate_consents(user_consents, scheme_id, JourneyTypes.JOIN.value)

                # Deserialize the user consent instances formatted to send to Midas
                user_consent_serializer = MidasUserConsentSerializer(user_consents, many=True)
                for user_consent in user_consents:
                    user_consent.save()

                data['credentials'].update(consents=user_consent_serializer.data)

            data['id'] = scheme_account.id
            if data['save_user_information']:
                self.save_user_profile(data['credentials'], request.user)

            self.post_midas_join(scheme_account, data['credentials'], join_scheme.slug, request.user.id)

            keys_to_remove = ['save_user_information', 'credentials']
            response_dict = {key: value for (key, value) in data.items() if key not in keys_to_remove}

            return response_dict, status.HTTP_201_CREATED
        except serializers.ValidationError:
            self.handle_failed_join(scheme_account)
            raise
        except Exception:
            self.handle_failed_join(scheme_account)
            return {'message': 'Unknown error with join'}, status.HTTP_200_OK

    @staticmethod
    def handle_failed_join(scheme_account):
        scheme_account_answers = scheme_account.schemeaccountcredentialanswer_set.all()
        [answer.delete() for answer in scheme_account_answers]

        scheme_account.status = SchemeAccount.JOIN
        scheme_account.save()
        sentry.captureException()

    @staticmethod
    def create_join_account(data, user, scheme_id):
        with transaction.atomic():
            try:
                scheme_account = SchemeAccount.objects.get(
                    user_set__id=user.id,
                    scheme_id=scheme_id,
                    status=SchemeAccount.JOIN
                )

                scheme_account.order = data['order']
                scheme_account.status = SchemeAccount.PENDING
                scheme_account.save()
            except SchemeAccount.DoesNotExist:
                scheme_account = SchemeAccount.objects.create(
                    scheme_id=data['scheme'],
                    order=data['order'],
                    status=SchemeAccount.PENDING
                )
                SchemeAccountEntry.objects.create(scheme_account=scheme_account, user=user)

        analytics.update_scheme_account_attribute(scheme_account, user)

        return scheme_account

    @staticmethod
    def save_user_profile(credentials, user):
        for question, answer in credentials.items():
            try:
                user.profile.set_field(question, answer)
            except AttributeError:
                continue
        user.profile.save()

    @staticmethod
    def post_midas_join(scheme_account, credentials_dict, slug, user_id):
        for question in scheme_account.scheme.link_questions:
            question_type = question.type
            SchemeAccountCredentialAnswer.objects.update_or_create(
                question=scheme_account.question(question_type),
                scheme_account=scheme_account,
                answer=credentials_dict[question_type])

        encrypted_credentials = AESCipher(
            settings.AES_KEY.encode()).encrypt(json.dumps(credentials_dict)).decode('utf-8')

        data = {
            'scheme_account_id': scheme_account.id,
            'credentials': encrypted_credentials,
            'user_id': user_id,
            'status': scheme_account.status,
            'journey_type': JourneyTypes.JOIN.value
        }
        headers = {"transaction": str(uuid.uuid1()), "User-agent": 'Hermes on {0}'.format(socket.gethostname())}
        response = requests.post('{}/{}/register'.format(settings.MIDAS_URL, slug), json=data, headers=headers)

        message = response.json().get('message')
        if not message == "success":
            raise RequestException(
                'Error creating join task in Midas. Response message :{}'.format(message)
            )


class UpdateCredentialsMixin:
    @staticmethod
    def update_credentials(scheme_account, data):
        serializer = UpdateCredentialSerializer(data=data, context={'scheme_account': scheme_account})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if 'consents' in data:
            data.pop('consents')

        updated_credentials = []

        for credential_type in data.keys():
            question = scheme_account.scheme.questions.get(type=credential_type)
            SchemeAccountCredentialAnswer.objects.update_or_create(question=question, scheme_account=scheme_account,
                                                                   defaults={'answer': data[credential_type]})
            updated_credentials.append(credential_type)

        return {'updated': updated_credentials}
