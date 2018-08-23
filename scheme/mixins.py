import json
import socket
import uuid

import requests
from django.conf import settings
from django.db import transaction
from raven.contrib.django.raven_compat.models import client as sentry
from requests import RequestException
from rest_framework import serializers, status
from rest_framework.generics import get_object_or_404

from intercom import intercom_api
from scheme.encyption import AESCipher
from scheme.models import ConsentStatus, Scheme, SchemeAccount, SchemeAccountCredentialAnswer, JourneyTypes
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
            user_consents = UserConsentSerializer.get_user_consents(scheme_account, consent_data)
            UserConsentSerializer.validate_consents(user_consents, scheme_account.scheme.id, JourneyTypes.LINK.value)

            user_consent_serializer = MidasUserConsentSerializer(user_consents, many=True)
            midas_consent_data = user_consent_serializer.data

        for answer_type, answer in data.items():
            SchemeAccountCredentialAnswer.objects.update_or_create(
                question=scheme_account.question(answer_type),
                scheme_account=scheme_account, defaults={'answer': answer})

        midas_information = scheme_account.get_midas_balance(user_consents=midas_consent_data)

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

        try:
            intercom_api.update_account_status_custom_attribute(settings.INTERCOM_TOKEN, scheme_account, user)
        except intercom_api.IntercomException:
            pass
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
    def create_account(self, data, user):
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # my360 schemes should never come through this endpoint
        scheme = Scheme.objects.get(id=data['scheme'])
        if scheme.url == settings.MY360_SCHEME_URL:
            try:
                metadata = {
                    'scheme name': scheme.name,
                }
                intercom_api.post_intercom_event(
                    settings.INTERCOM_TOKEN,
                    user.uid,
                    intercom_api.MY360_APP_EVENT,
                    metadata
                )

            except intercom_api.IntercomException:
                pass

            raise serializers.ValidationError({
                "non_field_errors": [
                    "Invalid Scheme: {}. Please use /schemes/accounts/my360 endpoint".format(scheme.slug)
                ]
            })
        answer_type = serializer.context['answer_type']
        try:
            query = {
                'scheme_account__scheme__id': data['scheme'],
                'answer': data[answer_type]
            }
            scheme_account = SchemeAccountCredentialAnswer.objects.get(**query).scheme_account
            data['id'] = scheme_account.id

            if scheme_account.is_deleted:
                scheme_account.is_deleted = False
                scheme_account.save()

            SchemeAccountEntry.objects.get_or_create(user=user, scheme_account=scheme_account)
            for card in scheme_account.payment_card_account_set.all():
                PaymentCardAccountEntry.objects.get_or_create(user=user, payment_card_account=card)

        except SchemeAccountCredentialAnswer.DoesNotExist:
            scheme_account = self._create_account(user, data, answer_type)

        return scheme_account, data

    @staticmethod
    def _create_account(user, data, answer_type):
        if type(data) == int:
            return data

        with transaction.atomic():
            try:
                scheme_account = SchemeAccount.objects.get(
                    user_set__id=user.id,
                    scheme_id=data['scheme'],
                    status=SchemeAccount.JOIN
                )

                scheme_account.order = data['order']
                scheme_account.status = SchemeAccount.WALLET_ONLY
                scheme_account.save()
            except SchemeAccount.DoesNotExist:
                scheme_account = SchemeAccount.objects.create(
                    scheme_id=data['scheme'],
                    order=data['order'],
                    status=SchemeAccount.WALLET_ONLY
                )
                SchemeAccountEntry.objects.create(scheme_account=scheme_account, user=user)

            SchemeAccountCredentialAnswer.objects.create(
                scheme_account=scheme_account,
                question=scheme_account.question(answer_type),
                answer=data[answer_type],
            )

            if 'consents' in data:
                user_consents = UserConsentSerializer.get_user_consents(scheme_account, data.pop('consents'))
                UserConsentSerializer.validate_consents(user_consents, scheme_account.scheme, JourneyTypes.ADD.value)
                for user_consent in user_consents:
                    user_consent.status = ConsentStatus.SUCCESS
                    user_consent.save()

        data['id'] = scheme_account.id
        try:
            intercom_api.update_account_status_custom_attribute(settings.INTERCOM_TOKEN, scheme_account, user)
        except intercom_api.IntercomException:
            pass

        return scheme_account


class SchemeAccountJoinMixin:

    def handle_join_request(self, request, *args, **kwargs):
        scheme_id = int(kwargs['pk'])
        join_scheme = get_object_or_404(Scheme.objects, id=scheme_id)
        serializer = JoinSerializer(data=request.data, context={
            'scheme': join_scheme,
            'user': request.user
        })
        serializer.is_valid(raise_exception=True)
        serializer.save()  # Save consents
        data = serializer.validated_data
        data['scheme'] = scheme_id
        scheme_account = self.create_join_account(data, request.user, scheme_id)
        try:
            data['id'] = scheme_account.id
            if data['save_user_information']:
                self.save_user_profile(data['credentials'], request.user)

            self.post_midas_join(scheme_account, data['credentials'], join_scheme.slug, request.user.id)

            keys_to_remove = ['save_user_information', 'credentials']
            response_dict = {key: value for (key, value) in data.items() if key not in keys_to_remove}

            return response_dict, status.HTTP_201_CREATED

        except Exception as e:
            scheme_account_answers = scheme_account.schemeaccountcredentialanswer_set.all()
            [answer.delete() for answer in scheme_account_answers]
            scheme_account.status = SchemeAccount.JOIN
            scheme_account.save()
            sentry.captureException()

            return {'message': 'Error with join'}, status.HTTP_200_OK

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

        try:
            intercom_api.update_account_status_custom_attribute(settings.INTERCOM_TOKEN, scheme_account, user)
        except intercom_api.IntercomException:
            pass

        return scheme_account

    @staticmethod
    def save_user_profile(credentials, user):
        for question, answer in credentials.items():
            try:
                setattr(user.profile, question, answer)
            except Exception:
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
            'user_id': user_id
        }
        headers = {"transaction": str(uuid.uuid1()), "User-agent": 'Hermes on {0}'.format(socket.gethostname())}
        response = requests.post('{}/{}/register'.format(settings.MIDAS_URL, slug),
                                 json=data, headers=headers)

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
        updated_credentials = []

        for credential_type in data.keys():
            question = scheme_account.scheme.questions.get(type=credential_type)
            SchemeAccountCredentialAnswer.objects.update_or_create(question=question, scheme_account=scheme_account,
                                                                   defaults={'answer': data[credential_type]})
            updated_credentials.append(credential_type)

        return {'updated': updated_credentials}
