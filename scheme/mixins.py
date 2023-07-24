import json
import logging
import typing as t
import uuid

import requests
import sentry_sdk
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError

from api_messaging.midas_messaging import send_midas_join_request
from hermes.channels import Permit
from history.tasks import add_auth_outcome_task, auth_outcome_task
from payment_card.payment import Payment, PaymentError
from scheme.credentials import (
    BARCODE,
    CARD_NUMBER,
    CASE_SENSITIVE_CREDENTIALS,
    ENCRYPTED_CREDENTIALS,
    MERCHANT_IDENTIFIER,
    PASSWORD,
    PASSWORD_2,
    PAYMENT_CARD_HASH,
)
from scheme.encryption import AESCipher
from scheme.models import (
    Consent,
    ConsentStatus,
    JourneyTypes,
    Scheme,
    SchemeAccount,
    SchemeAccountCredentialAnswer,
    SchemeCredentialQuestion,
    UserConsent,
)
from scheme.serializers import UbiquityJoinSerializer, UpdateCredentialSerializer, UserConsentSerializer
from ubiquity.channel_vault import AESKeyNames
from ubiquity.models import AccountLinkStatus, SchemeAccountEntry

DATAWAREHOUSE_EVENTS = {
    AccountLinkStatus.ADD_AUTH_PENDING: add_auth_outcome_task,
    AccountLinkStatus.AUTH_PENDING: auth_outcome_task,
}


if t.TYPE_CHECKING:
    from django.db.models import QuerySet
    from rest_framework.serializers import Serializer

    from user.models import CustomUser

logger = logging.getLogger(__name__)


class BaseLinkMixin(object):
    @staticmethod
    def link_account(
        serializer: "Serializer",
        scheme_account: SchemeAccount,
        user: "CustomUser",
        scheme_account_entry: "SchemeAccountEntry",
        headers: dict = None,
    ) -> dict:
        serializer.is_valid(raise_exception=True)
        return BaseLinkMixin._link_account(
            serializer.validated_data, scheme_account, user, scheme_account_entry, headers
        )

    @staticmethod
    def _link_account(
        data: dict,
        scheme_account: "SchemeAccount",
        user: "CustomUser",
        scheme_account_entry: "SchemeAccountEntry",
        headers: dict = None,
    ) -> dict:
        user_consents = []

        if "consents" in data:
            consent_data = data.pop("consents")
            scheme_consents = Consent.objects.filter(
                scheme=scheme_account.scheme.id, journey=JourneyTypes.LINK.value, check_box=True
            )

            user_consents = UserConsentSerializer.get_user_consents(scheme_account, consent_data, user, scheme_consents)
            UserConsentSerializer.validate_consents(
                user_consents, scheme_account.scheme.id, JourneyTypes.LINK.value, scheme_consents
            )

        for answer_type, answer in data.items():
            SchemeAccountCredentialAnswer.objects.update_or_create(
                question=scheme_account.question(answer_type),
                defaults={"answer": answer},
                scheme_account_entry=scheme_account_entry,
            )

        midas_information, dw_event = scheme_account.get_balance(scheme_account_entry, headers=headers)

        # dw_event is a two piece tuple, success: bool, journey: SchemeAccount STATUS
        #  - not present for cached balances only fresh crepes
        if dw_event:
            success, journey = dw_event
            DATAWAREHOUSE_EVENTS[journey].delay(
                success=success, scheme_account_entry=scheme_account_entry, headers=headers
            )

        response_data = {
            "balance": midas_information,
            "status": scheme_account_entry.link_status,
            "status_name": scheme_account_entry.status_name,
            "display_status": scheme_account_entry.display_status,
        }
        response_data.update(dict(data))

        if scheme_account.schemeaccountentry_set.filter(link_status=AccountLinkStatus.ACTIVE).exists():
            for user_consent in user_consents:
                user_consent.status = ConsentStatus.SUCCESS
                user_consent.save()
        else:
            user_consents = scheme_account.collect_pending_consents()
            for user_consent in user_consents:
                user_consent = UserConsent.objects.get(id=user_consent["id"])
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
        data = {"uuid": str(uuid.uuid4()), "base64img": base_64_image}
        headers = {"Content-Type": "application/json"}
        resp = requests.post(settings.HECATE_URL + "/classify", json=data, headers=headers)
        return resp.json()


class SchemeAccountCreationMixin(SwappableSerializerMixin):
    def get_validated_data(self, data: dict, user: "CustomUser") -> "Serializer":
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        # my360 schemes should never come through this endpoint
        scheme = Scheme.objects.get(id=data["scheme"])
        permit = self.request.channels_permit

        if permit and permit.is_scheme_suspended(scheme.id):
            raise serializers.ValidationError("This scheme is temporarily unavailable.")

        if scheme.url == settings.MY360_SCHEME_URL:
            raise serializers.ValidationError(
                {
                    "non_field_errors": [
                        "Invalid Scheme: {}. Please use /schemes/accounts/my360 endpoint".format(scheme.slug)
                    ]
                }
            )
        return serializer

    def create_account_with_valid_data(
        self, serializer: "Serializer", user: "CustomUser", scheme: Scheme
    ) -> t.Tuple[SchemeAccount, dict, bool, str, str, SchemeAccountEntry, bool]:
        data = serializer.validated_data
        answer_type = serializer.context["answer_type"]
        account_created = False
        main_answer_field = SchemeAccount.get_key_cred_field_from_question_type(answer_type)

        try:
            if answer_type not in CASE_SENSITIVE_CREDENTIALS:
                data[answer_type] = data[answer_type].lower()

            scheme_account = SchemeAccount.objects.get(**{"scheme": scheme, main_answer_field: data[answer_type]})
        except SchemeAccount.DoesNotExist:
            account_created = True
            scheme_account = self._create_new_account(user, scheme, data, answer_type)
            sae = SchemeAccountEntry.objects.create(scheme_account=scheme_account, user=user)
            resp = (scheme_account, data, account_created, answer_type, data[answer_type], sae, True)
        else:
            # removed handle_existing_scheme_account is called after this function as it just seemed
            # to set auth provided flag no longer used. Get or create is probably overkill as it should already be set
            sae, sae_created = SchemeAccountEntry.objects.get_or_create(user=user, scheme_account=scheme_account)
            resp = (scheme_account, data, account_created, answer_type, data[answer_type], sae, sae_created)

        data["id"] = scheme_account.id
        return resp

    def create_main_answer_credential(self, answer_type, scheme_account_entry, main_answer):
        SchemeAccountCredentialAnswer.objects.create(
            scheme_account_entry=scheme_account_entry,
            question=self._get_question_from_type(scheme_account_entry.scheme_account, answer_type),
            answer=main_answer,
        )
        scheme_account_entry.update_scheme_account_key_credential_fields()

    def _get_question_from_type(self, scheme_account: SchemeAccount, question_type: str) -> SchemeCredentialQuestion:
        if not hasattr(self, "scheme_questions"):
            return scheme_account.question(question_type)

        for question in self.scheme_questions:
            if question.type == question_type:
                return question

        raise SchemeCredentialQuestion.DoesNotExist(
            f"Could not find question of type: {question_type} for scheme: {scheme_account.scheme.slug}."
        )

    def _create_new_account(self, user: "CustomUser", scheme: Scheme, data: dict, answer_type: str) -> SchemeAccount:
        main_answer_field = SchemeAccount.get_key_cred_field_from_question_type(answer_type)

        with transaction.atomic():
            scheme_account = SchemeAccount.objects.create(
                scheme=scheme, order=data["order"], **{main_answer_field: data[answer_type]}
            )
            self.save_consents(user, scheme_account, data, JourneyTypes.LINK.value)
        return scheme_account

    def save_consents(self, user: "CustomUser", scheme_account: "SchemeAccount", data: dict, journey_type: int) -> None:
        if "consents" in data:
            if hasattr(self, "current_scheme"):
                scheme = self.current_scheme
            else:
                scheme = scheme_account.scheme

            scheme_consents = Consent.get_checkboxes_by_scheme_and_journey_type(
                scheme=scheme, journey_type=journey_type
            )
            user_consents = UserConsentSerializer.get_user_consents(
                scheme_account, data.pop("consents"), user, scheme_consents
            )
            UserConsentSerializer.validate_consents(user_consents, scheme, journey_type, scheme_consents)
            for user_consent in user_consents:
                user_consent.status = ConsentStatus.SUCCESS

            UserConsent.objects.bulk_create(user_consents)


class SchemeAccountJoinMixin:
    @staticmethod
    def validate(
        data: dict,
        scheme_account: "SchemeAccount",
        user: "CustomUser",
        permit: "Permit",
        join_scheme: Scheme,
        serializer_class=UbiquityJoinSerializer,
    ):
        if permit and permit.is_scheme_suspended(join_scheme.id):
            raise serializers.ValidationError("This scheme is temporarily unavailable.")

        serializer = serializer_class(data=data, context={"scheme": join_scheme, "user": user})
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        validated_data["scheme"] = join_scheme.id

        if not scheme_account:
            scheme_account = SchemeAccountJoinMixin.create_join_account(validated_data, user, join_scheme.id)

        if "consents" in validated_data:
            consent_data = validated_data["consents"]
            scheme_consents = Consent.objects.filter(
                scheme=join_scheme.id, journey=JourneyTypes.JOIN.value, check_box=True
            )

            user_consents = UserConsentSerializer.get_user_consents(
                scheme_account, consent_data, user, scheme_consents, join_scheme
            )
            UserConsentSerializer.validate_consents(
                user_consents, join_scheme.id, JourneyTypes.JOIN.value, scheme_consents
            )

        return validated_data, serializer, scheme_account

    def handle_join_request(
        self,
        data: dict,
        user: "CustomUser",
        scheme_id: int,
        scheme_account: SchemeAccount,
        serializer: "Serializer",
        channel: str,
        headers: dict = None,
    ) -> t.Tuple[dict, int, SchemeAccount]:
        scheme_account_entry = scheme_account.schemeaccountentry_set.get(user=user)
        scheme_account_entry.update_scheme_account_key_credential_fields()
        try:
            payment_card_hash = data["credentials"].get(PAYMENT_CARD_HASH)
            if payment_card_hash:
                Payment.process_payment_purchase(scheme_account, payment_card_hash, user.id, payment_amount=100)

            self.save_consents(serializer, user, scheme_account, scheme_id, data)

            data["id"] = scheme_account.id
            if data.get("save_user_information"):
                self.save_user_profile(data["credentials"], user)

            self.post_midas_join(
                scheme_account,
                data["credentials"],
                scheme_account.scheme.slug,
                user.id,
                channel,
                scheme_account_entry,
                headers=headers,
            )

            keys_to_remove = ["save_user_information", "credentials"]
            response_dict = {key: value for (key, value) in data.items() if key not in keys_to_remove}

            return response_dict, status.HTTP_201_CREATED, scheme_account
        except PaymentError:
            self.handle_failed_join(scheme_account, user, scheme_account_entry)
            raise
        except Exception as e:
            logger.exception(repr(e))
            self.handle_failed_join(scheme_account, user, scheme_account_entry)
            return {"message": "Unknown error with join"}, status.HTTP_200_OK, scheme_account

    @staticmethod
    def save_consents(serializer, user, scheme_account, scheme_id, data):
        if "consents" in serializer.validated_data:
            consent_data = serializer.validated_data.pop("consents")
            scheme_consents = Consent.objects.filter(
                scheme=scheme_account.scheme.id, journey=JourneyTypes.JOIN.value, check_box=True
            )

            user_consents = UserConsentSerializer.get_user_consents(scheme_account, consent_data, user, scheme_consents)
            UserConsentSerializer.validate_consents(user_consents, scheme_id, JourneyTypes.JOIN.value, scheme_consents)

            for user_consent in user_consents:
                user_consent.save()

            user_consents = scheme_account.format_user_consents([x.__dict__ for x in user_consents])
            data["credentials"].update(consents=user_consents)

    @staticmethod
    def handle_failed_join(
        scheme_account: SchemeAccount, user: "CustomUser", scheme_account_entry: "SchemeAccountEntry"
    ) -> None:
        queryset = scheme_account_entry.schemeaccountcredentialanswer_set
        card_number = scheme_account.card_number
        if card_number:
            queryset = queryset.exclude(answer=card_number)

        queryset.all().delete()
        scheme_account.userconsent_set.filter(status=ConsentStatus.PENDING).delete()

        Payment.process_payment_void(scheme_account)

        if card_number:
            scheme_account.status = AccountLinkStatus.REGISTRATION_FAILED
            scheme_account_entry.set_link_status(AccountLinkStatus.REGISTRATION_FAILED)
        else:
            scheme_account.status = AccountLinkStatus.ENROL_FAILED
            scheme_account_entry.set_link_status(AccountLinkStatus.ENROL_FAILED)
            scheme_account.alt_main_answer = ""
        scheme_account.save()
        sentry_sdk.capture_exception()

    @staticmethod
    def create_join_account(data: dict, user: "CustomUser", scheme_id: int) -> SchemeAccount:
        # todo: Needs a bit of thought in P3.

        with transaction.atomic():
            try:
                scheme_account_entry = SchemeAccountEntry.objects.get(
                    user=user,
                    scheme_account__scheme_id=scheme_id,
                    link_status__in=AccountLinkStatus.join_action_required(),
                )

                scheme_account_entry.scheme_account.order = data["order"]
                scheme_account_entry.scheme_account.save(update_fields=["order"])

                if scheme_account_entry:
                    scheme_account_entry.set_link_status(AccountLinkStatus.PENDING)

            except SchemeAccountEntry.DoesNotExist:
                scheme_account = SchemeAccount.objects.create(scheme_id=data["scheme"], order=data["order"])
                SchemeAccountEntry.objects.create(
                    scheme_account=scheme_account, user=user, link_status=AccountLinkStatus.PENDING
                )

        return scheme_account

    @staticmethod
    def save_user_profile(credentials: dict, user: "CustomUser") -> None:
        for question, answer in credentials.items():
            try:
                user.profile.set_field(question, answer)
            except AttributeError:
                continue
        user.profile.save()

    @staticmethod
    def post_midas_join(
        scheme_account: SchemeAccount,
        credentials_dict: dict,
        slug: str,
        user_id: int,
        channel: str,
        scheme_account_entry: SchemeAccountEntry,
        headers: dict = None,
    ) -> None:
        for question in scheme_account.scheme.link_questions:
            question_type = question.type

            if question_type in (PASSWORD, PASSWORD_2):
                if PASSWORD_2 in credentials_dict:
                    answer = credentials_dict[PASSWORD_2]
                    credentials_dict[PASSWORD] = credentials_dict.pop(PASSWORD_2)
                else:
                    answer = credentials_dict[PASSWORD]
            else:
                answer = credentials_dict[question_type]

            SchemeAccountCredentialAnswer.objects.update_or_create(
                question=scheme_account.question(question_type),
                defaults={"answer": answer},
                scheme_account_entry=scheme_account_entry,
            )

        updated_credentials = scheme_account_entry.update_or_create_primary_credentials(credentials_dict)

        encrypted_credentials = AESCipher(AESKeyNames.AES_KEY).encrypt(json.dumps(updated_credentials)).decode("utf-8")

        # via RabbitMQ
        send_midas_join_request(
            channel=channel,
            loyalty_plan=slug,
            bink_user_id=user_id,
            request_id=scheme_account.id,
            account_id=scheme_account.card_number or scheme_account.barcode or scheme_account.alt_main_answer,
            encrypted_credentials=encrypted_credentials,
            headers=headers,
        )


class UpdateCredentialsMixin:
    @staticmethod
    def _update_credentials(
        question_id_and_data: dict,
        existing_credentials: dict,
        scheme_account_entry: SchemeAccountEntry,
    ) -> list:
        create_credentials = []
        update_credentials = []
        updated_types = []
        for question_id, answer_and_type in question_id_and_data.items():
            question_type, new_answer = answer_and_type

            if question_type in ENCRYPTED_CREDENTIALS:
                new_answer = AESCipher(AESKeyNames.LOCAL_AES_KEY).encrypt(str(new_answer)).decode("utf-8")

            if question_id in existing_credentials:
                credential = existing_credentials[question_id]

                credential.answer = new_answer
                update_credentials.append(credential)

            else:
                create_credentials.append(
                    SchemeAccountCredentialAnswer(
                        question_id=question_id,
                        answer=new_answer,
                        scheme_account_entry=scheme_account_entry,
                    )
                )

            updated_types.append(question_type)

        if create_credentials:
            SchemeAccountCredentialAnswer.objects.bulk_create(create_credentials, ignore_conflicts=True)
        if update_credentials:
            SchemeAccountCredentialAnswer.objects.bulk_update(update_credentials, ["answer"])

        return updated_types

    def update_credentials(
        self,
        scheme_account: SchemeAccount,
        data: dict,
        scheme_account_entry: SchemeAccountEntry,
        questions=None,
        allow_existing_main_answer=True,
    ) -> dict:
        if questions is None:
            questions = (
                SchemeCredentialQuestion.objects.filter(scheme=scheme_account.scheme)
                .only("id", "type")
                .annotate(
                    is_main_question=Q(manual_question=True)
                    | Q(scan_question=True)
                    | Q(one_question_link=True)
                    | Q(type__in=[CARD_NUMBER, BARCODE, MERCHANT_IDENTIFIER])
                )
            )
        else:
            questions = questions.annotate(
                is_main_question=Q(manual_question=True)
                | Q(scan_question=True)
                | Q(one_question_link=True)
                | Q(type__in=[CARD_NUMBER, BARCODE, MERCHANT_IDENTIFIER])
            )

        serializer = UpdateCredentialSerializer(
            data=data,
            context={
                "questions": questions,
                "scheme_account_entry": scheme_account_entry,
                "allow_existing_main_answer": allow_existing_main_answer,
            },
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if "consents" in data:
            del data["consents"]

        question_id_from_type = {question.type: question.id for question in questions}
        existing_credentials = {
            credential.question_id: credential
            for credential in SchemeAccountCredentialAnswer.objects.filter(
                question_id__in=[question_id_from_type[credential_type] for credential_type in data.keys()],
                scheme_account_entry=scheme_account_entry,
            ).all()
        }
        question_id_and_data = {
            question_id_from_type[question_type]: (question_type, answer) for question_type, answer in data.items()
        }
        updated_types = self._update_credentials(
            question_id_and_data=question_id_and_data,
            existing_credentials=existing_credentials,
            scheme_account_entry=scheme_account_entry,
        )
        return {"updated": updated_types}

    def replace_credentials(
        self,
        scheme_account: SchemeAccount,
        data: dict,
        scheme: Scheme,
        scheme_account_entry: SchemeAccountEntry,
    ) -> dict:
        self._check_required_data_presence(scheme, data)

        scheme_account_entry.schemeaccountcredentialanswer_set.exclude(question__type__in=data.keys()).delete()
        return self.update_credentials(scheme_account, data, scheme_account_entry=scheme_account_entry)

    @staticmethod
    def get_existing_account_with_same_manual_answer(
        scheme_account: SchemeAccount, scheme_id: int, main_answer: str, main_answer_field: str
    ) -> bool:
        # i.e. if any schemeaccount exists with this main answer. This relies on main_answer always being populated,
        # which it SHOULD BE.
        account = (
            SchemeAccount.objects.filter(
                **{"scheme_id": scheme_id, "is_deleted": False, main_answer_field: main_answer}
            )
            .exclude(id=scheme_account.id)
            .all()
        )

        if len(account) > 1:
            raise ValidationError("More than one account already exists with this information")

        return account[0] if account else None

    @staticmethod
    def _get_new_answers(add_fields: dict, auth_fields: dict) -> t.Tuple[dict, str, str]:
        new_answers = {**add_fields, **auth_fields}

        add_fields.pop("consents", None)
        main_answer_field, *_ = add_fields.keys()
        main_answer_value = add_fields[main_answer_field]
        return new_answers, main_answer_field, main_answer_value

    @staticmethod
    def _filter_required_questions(required_questions: "QuerySet", scheme: Scheme, data: dict) -> "QuerySet":
        if scheme.manual_question and scheme.manual_question.type in data.keys():
            if scheme.scan_question:
                required_questions = required_questions.exclude(type=scheme.scan_question.type)
        elif scheme.scan_question and scheme.scan_question.type in data.keys():
            if scheme.manual_question:
                required_questions = required_questions.exclude(type=scheme.manual_question.type)

        return required_questions

    def _check_required_data_presence(self, scheme: Scheme, data: dict) -> None:
        if not self.request.channels_permit.permit_test_access(scheme):
            raise ValidationError(f"Scheme {scheme.id} not allowed for this user")

        if scheme.authorisation_required:
            query = Q(add_field=True) | Q(auth_field=True)
        else:
            query = Q(add_field=True)

        required_questions = scheme.questions.values("type").filter(query)
        filtered_required_questions = self._filter_required_questions(required_questions, scheme, data)

        for question in filtered_required_questions.all():
            if question["type"] not in data.keys():
                raise ValidationError(f'required field {question["type"]} is missing.')
