import json
import logging
import socket
import typing as t
import uuid

import requests
import sentry_sdk
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from requests import RequestException
from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError

import analytics
from hermes.channels import Permit
from payment_card.payment import Payment, PaymentError
from scheme.credentials import PAYMENT_CARD_HASH, CARD_NUMBER, BARCODE, ENCRYPTED_CREDENTIALS
from scheme.encyption import AESCipher
from scheme.models import (ConsentStatus, JourneyTypes, Scheme, SchemeAccount, SchemeAccountCredentialAnswer,
                           UserConsent, SchemeCredentialQuestion, Consent)
from scheme.serializers import (UbiquityJoinSerializer, UpdateCredentialSerializer,
                                UserConsentSerializer, LinkSchemeSerializer)
from ubiquity.models import SchemeAccountEntry

if t.TYPE_CHECKING:
    from user.models import CustomUser
    from rest_framework.serializers import Serializer
    from django.db.models import QuerySet

logger = logging.getLogger(__name__)


class BaseLinkMixin(object):

    @staticmethod
    def link_account(serializer: 'Serializer', scheme_account: SchemeAccount, user: 'CustomUser') -> dict:
        serializer.is_valid(raise_exception=True)
        return BaseLinkMixin._link_account(serializer.validated_data, scheme_account, user)

    @staticmethod
    def prepare_link_for_manual_check(auth_fields: dict, scheme_account: SchemeAccount) -> None:
        serializer = LinkSchemeSerializer(data=auth_fields, context={'scheme_account': scheme_account})
        serializer.is_valid(raise_exception=True)
        bink_users = [user for user in scheme_account.user_set.all() if user.client_id == settings.BINK_CLIENT_ID]
        for user in bink_users:
            analytics.api.update_scheme_account_attribute_new_status(
                scheme_account,
                user,
                dict(SchemeAccount.STATUSES).get(SchemeAccount.PENDING_MANUAL_CHECK))
        scheme_account.set_pending(manual_pending=True)
        data = serializer.validated_data

        for answer_type, answer in data.items():
            SchemeAccountCredentialAnswer.objects.update_or_create(
                question=scheme_account.question(answer_type),
                scheme_account=scheme_account, defaults={'answer': answer})

    @staticmethod
    def _link_account(data: dict, scheme_account: SchemeAccount, user: 'CustomUser') -> dict:
        user_consents = []

        if 'consents' in data:
            consent_data = data.pop('consents')
            scheme_consents = Consent.objects.filter(
                scheme=scheme_account.scheme.id,
                journey=JourneyTypes.LINK.value,
                check_box=True
            )

            user_consents = UserConsentSerializer.get_user_consents(scheme_account, consent_data, user, scheme_consents)
            UserConsentSerializer.validate_consents(
                user_consents, scheme_account.scheme.id, JourneyTypes.LINK.value, scheme_consents
            )

        for answer_type, answer in data.items():
            SchemeAccountCredentialAnswer.objects.update_or_create(
                question=scheme_account.question(answer_type),
                scheme_account=scheme_account, defaults={'answer': answer})

        midas_information = scheme_account.get_cached_balance()

        response_data = {
            'balance': midas_information,
            'status': scheme_account.status,
            'status_name': scheme_account.status_name,
            'display_status': scheme_account.display_status
        }
        response_data.update(dict(data))

        if scheme_account.status == SchemeAccount.ACTIVE:
            scheme_account.link_date = timezone.now()
            scheme_account.save(update_fields=['link_date'])

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
    def _get_scheme(base_64_image: str) -> dict:
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
    def get_validated_data(self, data: dict, user: 'CustomUser') -> 'Serializer':
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        # my360 schemes should never come through this endpoint
        scheme = Scheme.objects.get(id=data['scheme'])
        permit = self.request.channels_permit

        if permit and permit.is_scheme_suspended(scheme.id):
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

    def create_account(self, data: dict, user: 'CustomUser') -> t.Tuple[SchemeAccount, dict, bool]:
        serializer = self.get_validated_data(data, user)
        scheme = Scheme.get_scheme_and_questions_by_scheme_id(data['scheme'])
        return self.create_account_with_valid_data(serializer, user, scheme)

    def create_account_with_valid_data(
            self, serializer: 'Serializer', user: 'CustomUser', scheme: Scheme
    ) -> t.Tuple[SchemeAccount, dict, bool]:
        data = serializer.validated_data
        answer_type = serializer.context['answer_type']
        account_created = False

        try:
            join_account = user.scheme_account_set.get(
                scheme=scheme,
                status__in=SchemeAccount.JOIN_ACTION_REQUIRED
            )
            scheme_account = self._update_join_account(user, join_account, data, answer_type)
            resp = (scheme_account, data, account_created)

        except SchemeAccount.DoesNotExist:

            if answer_type in [CARD_NUMBER, BARCODE]:
                main_answer = answer_type
            else:
                main_answer = 'main_answer'

            try:
                scheme_account = SchemeAccount.objects.get(**{
                    'scheme': scheme,
                    main_answer: data[answer_type]
                })
            except SchemeAccount.DoesNotExist:
                account_created = True
                scheme_account = self._create_new_account(user, scheme, data, answer_type)
                resp = (scheme_account, data, account_created)
            else:
                # handle_existing_scheme_account is called after this function
                # to check if auth_fields match and link to user if not linked already
                resp = (scheme_account, data, account_created)

        data["id"] = scheme_account.id
        return resp

    def _get_question_from_type(self, scheme_account: SchemeAccount, question_type: str) -> SchemeCredentialQuestion:
        if not hasattr(self, 'scheme_questions'):
            return scheme_account.question(question_type)

        for question in self.scheme_questions:
            if question.type == question_type:
                return question

        raise SchemeCredentialQuestion.DoesNotExist(
            f'Could not find question of type: {question_type} for scheme: {scheme_account.scheme.slug}.'
        )

    def _create_new_account(self, user: 'CustomUser', scheme: Scheme, data: dict, answer_type: str) -> SchemeAccount:
        with transaction.atomic():
            scheme_account = SchemeAccount.objects.create(
                scheme=scheme,
                order=data['order'],
                status=SchemeAccount.WALLET_ONLY,
                main_answer=data[answer_type]
            )
            SchemeAccountEntry.objects.create(scheme_account=scheme_account, user=user)
            SchemeAccountCredentialAnswer.objects.create(
                scheme_account=scheme_account,
                question=self._get_question_from_type(scheme_account, answer_type),
                answer=data[answer_type]
            )
            self.analytics_update(user, scheme_account, acc_created=True)
            self.save_consents(user, scheme_account, data, JourneyTypes.LINK.value)
        return scheme_account

    def _update_join_account(
        self,
        user: 'CustomUser',
        scheme_account: 'SchemeAccount',
        data: dict,
        answer_type: str
    ) -> SchemeAccount:
        with transaction.atomic():
            scheme_account.order = data['order']
            scheme_account.status = SchemeAccount.WALLET_ONLY
            scheme_account.save()

            SchemeAccountCredentialAnswer.objects.create(
                scheme_account=scheme_account,
                question=self._get_question_from_type(scheme_account, answer_type),
                answer=data[answer_type],
            )

            self.analytics_update(user, scheme_account, acc_created=False)
            self.save_consents(user, scheme_account, data, JourneyTypes.JOIN.value)

        return scheme_account

    @staticmethod
    def analytics_update(user: 'CustomUser', scheme_account: 'SchemeAccount', acc_created: bool) -> None:
        if user.client_id == settings.BINK_CLIENT_ID:
            if acc_created:
                analytics.update_scheme_account_attribute(scheme_account, user)
            else:
                # Assume an update of a join account
                analytics.update_scheme_account_attribute(
                    scheme_account,
                    user,
                    old_status=dict(SchemeAccount.STATUSES).get(SchemeAccount.JOIN)
                )

    def save_consents(
        self, user: 'CustomUser', scheme_account: 'SchemeAccount', data: dict, journey_type: JourneyTypes
    ) -> None:
        if 'consents' in data:
            if hasattr(self, 'current_scheme'):
                scheme = self.current_scheme
            else:
                scheme = scheme_account.scheme

            scheme_consents = Consent.objects.filter(
                scheme=scheme_account.scheme_id,
                journey=journey_type,
                check_box=True
            ).all()
            user_consents = UserConsentSerializer.get_user_consents(
                scheme_account, data.pop('consents'), user, scheme_consents
            )
            UserConsentSerializer.validate_consents(user_consents, scheme, journey_type, scheme_consents)
            for user_consent in user_consents:
                user_consent.status = ConsentStatus.SUCCESS

            UserConsent.objects.bulk_create(user_consents)


class SchemeAccountJoinMixin:
    @staticmethod
    def validate(data: dict, scheme_account: 'SchemeAccount', user: 'CustomUser', permit: 'Permit',
                 join_scheme: Scheme, serializer_class=UbiquityJoinSerializer):

        if permit and permit.is_scheme_suspended(join_scheme.id):
            raise serializers.ValidationError('This scheme is temporarily unavailable.')

        serializer = serializer_class(data=data, context={
            'scheme': join_scheme,
            'user': user
        })
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        validated_data['scheme'] = join_scheme.id

        if not scheme_account:
            scheme_account = SchemeAccountJoinMixin.create_join_account(validated_data, user, join_scheme.id)

        if 'consents' in validated_data:
            consent_data = validated_data['consents']
            scheme_consents = Consent.objects.filter(
                scheme=join_scheme.id,
                journey=JourneyTypes.JOIN.value,
                check_box=True
            )

            user_consents = UserConsentSerializer.get_user_consents(
                scheme_account, consent_data, user, scheme_consents, join_scheme
            )
            UserConsentSerializer.validate_consents(
                user_consents, join_scheme.id, JourneyTypes.JOIN.value, scheme_consents
            )

        return validated_data, serializer, scheme_account

    def handle_join_request(self, data: dict, user: 'CustomUser', scheme_id: int, scheme_account: SchemeAccount,
                            serializer: 'Serializer', channel: str) -> t.Tuple[dict, int, SchemeAccount]:

        scheme_account.update_barcode_and_card_number()
        try:
            payment_card_hash = data['credentials'].get(PAYMENT_CARD_HASH)
            if payment_card_hash:
                Payment.process_payment_purchase(scheme_account, payment_card_hash, user.id, payment_amount=100)

            self.save_consents(serializer, user, scheme_account, scheme_id, data)

            data['id'] = scheme_account.id
            if data.get('save_user_information'):
                self.save_user_profile(data['credentials'], user)

            self.post_midas_join(scheme_account, data['credentials'], scheme_account.scheme.slug, user.id, channel)

            keys_to_remove = ['save_user_information', 'credentials']
            response_dict = {key: value for (key, value) in data.items() if key not in keys_to_remove}

            return response_dict, status.HTTP_201_CREATED, scheme_account
        except PaymentError:
            self.handle_failed_join(scheme_account, user)
            raise
        except Exception as e:
            logger.exception(repr(e))
            self.handle_failed_join(scheme_account, user)
            return {'message': 'Unknown error with join'}, status.HTTP_200_OK, scheme_account

    @staticmethod
    def save_consents(serializer, user, scheme_account, scheme_id, data):
        if 'consents' in serializer.validated_data:
            consent_data = serializer.validated_data.pop('consents')
            scheme_consents = Consent.objects.filter(
                scheme=scheme_account.scheme.id,
                journey=JourneyTypes.JOIN.value,
                check_box=True
            )

            user_consents = UserConsentSerializer.get_user_consents(scheme_account, consent_data, user, scheme_consents)
            UserConsentSerializer.validate_consents(user_consents, scheme_id, JourneyTypes.JOIN.value, scheme_consents)

            for user_consent in user_consents:
                user_consent.save()

            user_consents = scheme_account.format_user_consents([x.__dict__ for x in user_consents])
            data['credentials'].update(consents=user_consents)

    @staticmethod
    def handle_failed_join(scheme_account: SchemeAccount, user: 'CustomUser') -> None:
        queryset = scheme_account.schemeaccountcredentialanswer_set
        card_number = scheme_account.card_number
        if card_number:
            queryset = queryset.exclude(answer=card_number)

        queryset.all().delete()
        scheme_account.userconsent_set.filter(status=ConsentStatus.PENDING).delete()

        if user.client_id == settings.BINK_CLIENT_ID:
            analytics.update_scheme_account_attribute(
                scheme_account,
                user,
                dict(SchemeAccount.STATUSES).get(SchemeAccount.JOIN))

        Payment.process_payment_void(scheme_account)

        if card_number:
            scheme_account.status = SchemeAccount.REGISTRATION_FAILED
        else:
            scheme_account.status = SchemeAccount.ENROL_FAILED
            scheme_account.main_answer = ""
        scheme_account.save()
        sentry_sdk.capture_exception()

    @staticmethod
    def create_join_account(data: dict, user: 'CustomUser', scheme_id: int) -> SchemeAccount:
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
            analytics.update_scheme_account_attribute(
                scheme_account,
                user,
                dict(SchemeAccount.STATUSES).get(SchemeAccount.JOIN))
        elif user.client_id == settings.BINK_CLIENT_ID:
            analytics.update_scheme_account_attribute(scheme_account, user)

        return scheme_account

    @staticmethod
    def save_user_profile(credentials: dict, user: 'CustomUser') -> None:
        for question, answer in credentials.items():
            try:
                user.profile.set_field(question, answer)
            except AttributeError:
                continue
        user.profile.save()

    @staticmethod
    def post_midas_join(scheme_account: SchemeAccount, credentials_dict: dict, slug: str, user_id: int, channel: str
                        ) -> None:
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
            'journey_type': JourneyTypes.JOIN.value,
            'channel': channel
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
    def _update_credentials(
            scheme_account: SchemeAccount,
            question_id_and_data: dict,
            existing_credentials: dict
    ) -> list:
        create_credentials = []
        update_credentials = []
        updated_types = []
        main_answer = scheme_account.main_answer
        for question_id, answer_and_type in question_id_and_data.items():
            question_type, new_answer = answer_and_type

            if question_type in ENCRYPTED_CREDENTIALS:
                new_answer = AESCipher(settings.LOCAL_AES_KEY.encode()).encrypt(str(new_answer)).decode("utf-8")

            if question_id in existing_credentials:
                credential = existing_credentials[question_id]

                if credential.answer == main_answer and new_answer != main_answer:
                    scheme_account.main_answer = new_answer
                    scheme_account.save(update_fields=['main_answer'])

                credential.answer = new_answer
                update_credentials.append(credential)

            else:
                create_credentials.append(
                    SchemeAccountCredentialAnswer(
                        question_id=question_id,
                        scheme_account=scheme_account,
                        answer=new_answer
                    )
                )

            updated_types.append(question_type)

        if create_credentials:
            SchemeAccountCredentialAnswer.objects.bulk_create(create_credentials)
        if update_credentials:
            SchemeAccountCredentialAnswer.objects.bulk_update(update_credentials, ['answer'])

        return updated_types

    def update_credentials(self, scheme_account: SchemeAccount, data: dict, questions=None) -> dict:
        if questions is None:
            questions = SchemeCredentialQuestion.objects.filter(scheme=scheme_account.scheme).only("id", "type")

        serializer = UpdateCredentialSerializer(data=data, context={'questions': questions})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if 'consents' in data:
            del data['consents']

        question_id_from_type = {
            question.type: question.id
            for question in questions
        }
        existing_credentials = {
            credential.question_id: credential
            for credential in SchemeAccountCredentialAnswer.objects.filter(
                question_id__in=[question_id_from_type[credential_type] for credential_type in data.keys()],
                scheme_account=scheme_account
            ).all()
        }
        question_id_and_data = {
            question_id_from_type[question_type]: (question_type, answer)
            for question_type, answer in data.items()
        }
        updated_types = self._update_credentials(
            scheme_account=scheme_account,
            question_id_and_data=question_id_and_data,
            existing_credentials=existing_credentials
        )
        return {'updated': updated_types}

    def replace_credentials_and_scheme(self, scheme_account: SchemeAccount, data: dict, scheme: Scheme) -> dict:
        self._check_required_data_presence(scheme, data)

        if scheme_account.scheme != scheme:
            scheme_account.scheme = scheme
            scheme_account.save()

        scheme_account.schemeaccountcredentialanswer_set.exclude(question__type__in=data.keys()).delete()
        return self.update_credentials(scheme_account, data)

    @staticmethod
    def card_with_same_data_already_exists(account: SchemeAccount, scheme_id: int, main_answer: str) -> bool:
        return SchemeAccountCredentialAnswer.objects.filter(
            scheme_account__scheme_id=scheme_id,
            scheme_account__is_deleted=False,
            answer=main_answer
        ).exclude(
            scheme_account=account
        ).exists()

    @staticmethod
    def _get_new_answers(add_fields: dict, auth_fields: dict) -> t.Tuple[dict, str]:
        new_answers = {**add_fields, **auth_fields}

        add_fields.pop("consents", None)
        main_answer, *_ = add_fields.values()
        return new_answers, main_answer

    @staticmethod
    def _filter_required_questions(required_questions: 'QuerySet', scheme: Scheme, data: dict) -> 'QuerySet':
        if scheme.manual_question and scheme.manual_question.type in data.keys():
            if scheme.scan_question:
                required_questions = required_questions.exclude(type=scheme.scan_question.type)
        elif scheme.scan_question and scheme.scan_question.type in data.keys():
            if scheme.manual_question:
                required_questions = required_questions.exclude(type=scheme.manual_question.type)

        return required_questions

    def _check_required_data_presence(self, scheme: Scheme, data: dict) -> None:
        if not self.request.user.is_tester and scheme.test_scheme:
            raise ValidationError(f'Scheme {scheme.id} not allowed for this user')

        if scheme.authorisation_required:
            query = Q(add_field=True) | Q(auth_field=True)
        else:
            query = Q(add_field=True)

        required_questions = scheme.questions.values('type').filter(query)
        filtered_required_questions = self._filter_required_questions(required_questions, scheme, data)

        for question in filtered_required_questions.all():
            if question['type'] not in data.keys():
                raise ValidationError(f'required field {question["type"]} is missing.')
