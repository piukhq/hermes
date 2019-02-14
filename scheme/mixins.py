import json
import socket
import uuid

from django.conf import settings
from django.db import transaction
from raven.contrib.django.raven_compat.models import client as sentry
from requests import RequestException
from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import get_object_or_404

import analytics
from hermes.traced_requests import requests
from scheme.encyption import AESCipher
from scheme.models import (ConsentStatus, JourneyTypes, Scheme, SchemeAccount, SchemeAccountCredentialAnswer,
                           SchemeCredentialQuestion, UserConsent)
from scheme.serializers import (JoinSerializer, UpdateCredentialSerializer,
                                UserConsentSerializer, LinkSchemeSerializer)
from ubiquity.models import SchemeAccountEntry


class BaseLinkMixin(object):

    @staticmethod
    def link_account(serializer, scheme_account, user):
        serializer.is_valid(raise_exception=True)
        return BaseLinkMixin._link_account(serializer.validated_data, scheme_account, user)

    @staticmethod
    def prepare_link_for_manual_check(auth_fields, scheme_account):
        serializer = LinkSchemeSerializer(data=auth_fields, context={'scheme_account': scheme_account})
        serializer.is_valid(raise_exception=True)
        scheme_account.set_pending(manual_pending=True)
        data = serializer.validated_data

        for answer_type, answer in data.items():
            SchemeAccountCredentialAnswer.objects.update_or_create(
                question=scheme_account.question(answer_type),
                scheme_account=scheme_account, defaults={'answer': answer})

    @staticmethod
    def _link_account(data, scheme_account, user):
        user_consents = []

        if 'consents' in data:
            consent_data = data.pop('consents')
            user_consents = UserConsentSerializer.get_user_consents(scheme_account, consent_data, user)
            UserConsentSerializer.validate_consents(user_consents, scheme_account.scheme.id, JourneyTypes.LINK.value)

        for answer_type, answer in data.items():
            SchemeAccountCredentialAnswer.objects.update_or_create(
                question=scheme_account.question(answer_type),
                scheme_account=scheme_account, defaults={'answer': answer})

        midas_information = scheme_account.get_midas_balance(journey=JourneyTypes.LINK)

        response_data = {
            'balance': midas_information,
            'status': scheme_account.status,
            'status_name': scheme_account.status_name,
            'display_status': scheme_account.display_status
        }
        response_data.update(dict(data))

        if scheme_account.status == SchemeAccount.ACTIVE:
            for user_consent in user_consents:
                user_consent.status = ConsentStatus.SUCCESS
                user_consent.save()
        else:
            user_consents = scheme_account.collect_pending_consents()
            for user_consent in user_consents:
                user_consent = UserConsent.objects.get(id=user_consent['id'])
                user_consent.delete()

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

        if scheme.status == Scheme.SUSPENDED:
            raise serializers.ValidationError('This scheme is temporarily unavailable.')

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
            scheme_account = SchemeAccount.objects.filter(**query).distinct().get()

            if user.client_id == settings.ALLOWED_CLIENT_ID:
                return scheme_account, data, account_created

            raise ValidationError('Scheme Account already exists in another wallet.')
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
            scheme_account_updated = False
            try:
                scheme_account = SchemeAccount.objects.get(
                    user_set__id=user.id,
                    scheme_id=data['scheme'],
                    status__in=SchemeAccount.JOIN_ACTION_REQUIRED,
                    is_deleted=False
                )

                scheme_account.order = data['order']
                scheme_account.status = SchemeAccount.WALLET_ONLY
                scheme_account.save()
                scheme_account_updated = True

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

            finally:
                if user.client_id == settings.BINK_CLIENT_ID:
                    if scheme_account_updated:
                        analytics.update_scheme_account_attribute(scheme_account, user, SchemeAccount.JOIN)
                    elif account_created:
                        analytics.update_scheme_account_attribute(scheme_account, user)

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

        return scheme_account, account_created


class SchemeAccountJoinMixin:

    def handle_join_request(self, request, *args, **kwargs):
        scheme_id = int(kwargs['pk'])
        join_scheme = get_object_or_404(Scheme.objects, id=scheme_id)

        if join_scheme.status == Scheme.SUSPENDED:
            raise serializers.ValidationError('This scheme is temporarily unavailable.')

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

                for user_consent in user_consents:
                    user_consent.save()

                user_consents = scheme_account.collect_pending_consents()
                data['credentials'].update(consents=user_consents)

            data['id'] = scheme_account.id
            if data['save_user_information']:
                self.save_user_profile(data['credentials'], request.user)

            self.post_midas_join(scheme_account, data['credentials'], join_scheme.slug, request.user.id)

            keys_to_remove = ['save_user_information', 'credentials']
            response_dict = {key: value for (key, value) in data.items() if key not in keys_to_remove}

            return response_dict, status.HTTP_201_CREATED
        except serializers.ValidationError:
            self.handle_failed_join(scheme_account, request.user)
            raise
        except Exception:
            self.handle_failed_join(scheme_account, request.user)
            return {'message': 'Unknown error with join'}, status.HTTP_200_OK

    @staticmethod
    def handle_failed_join(scheme_account, user):
        scheme_account_answers = scheme_account.schemeaccountcredentialanswer_set.all()
        for answer in scheme_account_answers:
            answer.delete()

        scheme_account.userconsent_set.filter(status=ConsentStatus.PENDING).delete()

        if user.client_id == settings.BINK_CLIENT_ID:
            analytics.update_scheme_account_attribute(scheme_account, user, SchemeAccount.JOIN)

        scheme_account.status = SchemeAccount.JOIN
        scheme_account.save()
        sentry.captureException()

    @staticmethod
    def create_join_account(data, user, scheme_id):

        update = False

        with transaction.atomic():
            try:
                scheme_account = SchemeAccount.objects.get(
                    user_set__id=user.id,
                    scheme_id=scheme_id,
                    status__in=SchemeAccount.JOIN_ACTION_REQUIRED
                )

                scheme_account.order = data['order']
                scheme_account.status = SchemeAccount.PENDING
                scheme_account.save()
                update = True
            except SchemeAccount.DoesNotExist:
                scheme_account = SchemeAccount.objects.create(
                    scheme_id=data['scheme'],
                    order=data['order'],
                    status=SchemeAccount.PENDING
                )
                SchemeAccountEntry.objects.create(scheme_account=scheme_account, user=user)

        if user.client_id == settings.BINK_CLIENT_ID and update:
            analytics.update_scheme_account_attribute(scheme_account, user, SchemeAccount.JOIN)
        elif user.client_id == settings.BINK_CLIENT_ID:
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
                defaults={'answer': credentials_dict[question_type]}
            )

        updated_credentials = scheme_account.update_or_create_primary_credentials(credentials_dict)

        encrypted_credentials = AESCipher(
            settings.AES_KEY.encode()).encrypt(json.dumps(updated_credentials)).decode('utf-8')

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
        """
        :type scheme_account: scheme.models.SchemeAccount
        :type data: dict
        :rtype: dict
        """
        serializer = UpdateCredentialSerializer(data=data, context={'scheme_account': scheme_account})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if 'consents' in data:
            del data['consents']

        updated_credentials = []

        for credential_type in data.keys():
            question = scheme_account.scheme.questions.get(type=credential_type)
            SchemeAccountCredentialAnswer.objects.update_or_create(question=question, scheme_account=scheme_account,
                                                                   defaults={'answer': data[credential_type]})
            updated_credentials.append(credential_type)

        return {'updated': updated_credentials}

    def replace_credentials_and_scheme(self, scheme_account, data, scheme_id):
        """
        :type scheme_account: scheme.models.SchemeAccount
        :type data: dict
        :type scheme_id: int
        """
        scheme = get_object_or_404(Scheme, id=scheme_id)
        self._check_required_data_presence(scheme, data)

        if scheme_account.scheme != scheme:
            scheme_account.scheme = scheme
            scheme_account.save()

        scheme_account.schemeaccountcredentialanswer_set.all().delete()
        return self.update_credentials(scheme_account, data)

    @staticmethod
    def card_with_same_data_already_exists(account, scheme_id, main_answer):
        """
        :type account: scheme.models.SchemeAccount
        :type scheme_id: int
        :type main_answer: string
        :return:
        """
        query = {
            'scheme_account__scheme': scheme_id,
            'scheme_account__is_deleted': False,
            'answer': main_answer
        }
        exclude = {
            'scheme_account': account
        }

        if SchemeAccountCredentialAnswer.objects.filter(**query).exclude(**exclude).exists():
            return True

        return False

    @staticmethod
    def _get_new_answers(serializer, auth_fields):
        """
        :type serializer: ubiquity.serializers.UbiquityCreateSchemeAccountSerializer
        :type auth_fields: dict
        :rtype: (dict, int, str)
        """
        data = serializer.validated_data
        scheme_id = data.pop('scheme')
        del data['order']
        new_answers = {**data, **auth_fields}
        main_answer, *_ = data.values()

        return new_answers, scheme_id, main_answer

    @staticmethod
    def _check_required_data_presence(scheme, data):
        """
        :type scheme: scheme.models.Scheme
        :type data: dict
        """

        query_value = [SchemeCredentialQuestion.ADD_FIELD, ]
        if scheme.authorisation_required:
            query_value.append(SchemeCredentialQuestion.AUTH_FIELD)

        required_questions = scheme.questions.values('type').filter(field_type__in=query_value).all()
        for question in required_questions:
            if question['type'] not in data.keys():
                raise ValidationError('required field {} is missing.'.format(question['type']))
