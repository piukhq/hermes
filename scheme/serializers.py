import logging
from copy import copy

from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers

from common.models import Image
from scheme.credentials import BARCODE, CARD_NUMBER, CASE_SENSITIVE_CREDENTIALS, MERCHANT_IDENTIFIER
from scheme.models import (
    Consent,
    ConsentStatus,
    Control,
    Exchange,
    Scheme,
    SchemeAccount,
    SchemeAccountCredentialAnswer,
    SchemeAccountImage,
    SchemeCredentialQuestion,
    SchemeImage,
    UserConsent,
)
from ubiquity.models import AccountLinkStatus, SchemeAccountEntry
from user.models import CustomUser

logger = logging.getLogger(__name__)


class SchemeImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchemeImage
        exclude = ("scheme",)


class SchemeAccountImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchemeAccountImage
        fields = "__all__"


class QuestionSerializer(serializers.ModelSerializer):
    required = serializers.BooleanField()
    question_choices = serializers.ListField()

    class Meta:
        model = SchemeCredentialQuestion
        exclude = ("scheme", "manual_question", "scan_question", "one_question_link", "options")


class ConsentsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Consent
        exclude = ("is_enabled", "scheme", "created_on", "modified_on")


class ControlSerializer(serializers.ModelSerializer):
    class Meta:
        model = Control
        exclude = ("id", "scheme")


class TransactionHeaderSerializer(serializers.Serializer):
    """This serializer is required to convert a list of header titles into a
    form which the front end requires ie a list of key pairs where the key is
    a keyword "name" and the value is the header title.
    This is a departure from rest mapping to the model and was agreed with Paul Batty.
    Any serializer requiring transaction headers in this form should use
    transaction_headers = TransactionHeaderSerializer() otherwise transaction_headers will
    be represented by a simple list of headers.
    """

    def to_representation(self, obj):
        return [{"name": i} for i in obj]


class SchemeSerializer(serializers.ModelSerializer):
    images = SchemeImageSerializer(many=True, read_only=True)
    link_questions = serializers.SerializerMethodField()
    join_questions = serializers.SerializerMethodField()
    transaction_headers = TransactionHeaderSerializer()
    manual_question = QuestionSerializer()
    one_question_link = QuestionSerializer()
    scan_question = QuestionSerializer()
    consents = ConsentsSerializer(many=True, read_only=True)
    status = serializers.SerializerMethodField()
    is_active = serializers.SerializerMethodField()

    class Meta:
        model = Scheme
        exclude = ("card_number_prefix", "card_number_regex", "barcode_regex", "barcode_prefix")

    def get_is_active(self, obj):
        if self.context and self.context.get("request"):
            return self.context["request"].channels_permit.is_scheme_available(obj.id)
        # If no context return true as default case is that the SchemeBundleAssociation Status is not INACTIVE
        return True

    def get_status(self, obj):
        return self.context["request"].channels_permit.scheme_status(obj.id)

    @staticmethod
    def get_link_questions(obj):
        serializer = QuestionSerializer(obj.link_questions, many=True)
        return serializer.data

    @staticmethod
    def get_join_questions(obj):
        serializer = QuestionSerializer(obj.join_questions, many=True)
        return serializer.data


class SchemeSerializerNoQuestions(serializers.ModelSerializer):
    transaction_headers = TransactionHeaderSerializer()
    is_active = serializers.SerializerMethodField()

    class Meta:
        model = Scheme
        exclude = ("card_number_prefix", "card_number_regex", "barcode_regex", "barcode_prefix")

    def get_is_active(self, obj):
        return self.context["request"].channels_permit.is_scheme_active(obj.id)


class UserConsentSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    value = serializers.BooleanField()

    @staticmethod
    def get_user_consents(scheme_account, consent_data, user, scheme_consents, scheme=None):
        """
        Returns UserConsent instances from the data sent by the frontend (Consent id and a value of true/false.)
        if the consent id is available in the provided scheme consents.
        These are not yet saved to the database.
        """
        scheme = scheme or scheme_account.scheme

        provided_consents = []
        for data in consent_data:
            for consent in scheme_consents:
                if data["id"] == consent.id:
                    consent_info = {"value": data["value"], "consent": consent}
                    provided_consents.append(consent_info)

        user_consents = []
        for consent_info in provided_consents:
            value = consent_info["value"]

            user_consent = UserConsent(
                scheme_account=scheme_account,
                value=value,
                slug=consent_info["consent"].slug,
                user=user,
                created_on=timezone.now(),
                scheme=scheme,
            )

            serializer = ConsentsSerializer(consent_info["consent"])
            user_consent.metadata = serializer.data
            user_consent.metadata.update({"user_email": user.email, "scheme_slug": scheme.slug})

            user_consents.append(user_consent)

        return user_consents

    @staticmethod
    def validate_consents(user_consents, scheme, journey_type, scheme_consents):
        # Validate correct number of user_consents provided
        expected_consents_set = {consent.slug for consent in scheme_consents}

        if len(expected_consents_set) != len(user_consents):
            raise serializers.ValidationError(
                {
                    "message": "Incorrect number of consents provided for this scheme and journey type.",
                    "code": serializers.ValidationError.status_code,
                }
            )

        # Validate slugs match those expected for slug + journey
        actual_consents_set = {user_consent.slug for user_consent in user_consents}

        if expected_consents_set.symmetric_difference(actual_consents_set):
            raise serializers.ValidationError(
                {
                    "message": "Unexpected or missing user consents for '{0}' request - scheme id '{1}'".format(
                        Consent.journeys[journey_type][1], scheme
                    ),
                    "code": serializers.ValidationError.status_code,
                }
            )

        # Validate that the user consents for all required consents have a value of True
        invalid_consents = [
            {"consent_id": consent.metadata["id"], "slug": consent.slug}
            for consent in user_consents
            if consent.metadata["required"] is True and consent.value is False
        ]

        if invalid_consents:
            raise serializers.ValidationError(
                {
                    "message": "The following consents require a value of True: {}".format(invalid_consents),
                    "code": serializers.ValidationError.status_code,
                }
            )

        return user_consents


class SchemeAnswerSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=250, required=False)
    card_number = serializers.CharField(max_length=250, required=False)
    barcode = serializers.CharField(max_length=250, required=False)
    password = serializers.CharField(max_length=250, required=False)
    password_2 = serializers.CharField(max_length=250, required=False)
    place_of_birth = serializers.CharField(max_length=250, required=False)
    email = serializers.EmailField(max_length=250, required=False)
    postcode = serializers.CharField(max_length=250, required=False)
    memorable_date = serializers.DateField(input_formats=["%d/%m/%Y"], required=False)
    pin = serializers.RegexField(r"^[0-9]+", max_length=250, required=False)
    title = serializers.CharField(max_length=250, required=False)
    first_name = serializers.CharField(max_length=250, required=False)
    last_name = serializers.CharField(max_length=250, required=False)
    favourite_place = serializers.CharField(max_length=250, required=False)
    date_of_birth = serializers.DateField(input_formats=["%d/%m/%Y"], required=False)
    phone = serializers.CharField(max_length=250, required=False)
    phone_2 = serializers.CharField(max_length=250, required=False)
    gender = serializers.CharField(max_length=250, required=False)
    address_1 = serializers.CharField(max_length=250, required=False)
    address_2 = serializers.CharField(max_length=250, required=False)
    address_3 = serializers.CharField(max_length=250, required=False)
    town_city = serializers.CharField(max_length=250, required=False)
    county = serializers.CharField(max_length=250, required=False)
    country = serializers.CharField(max_length=250, required=False)
    regular_restaurant = serializers.CharField(max_length=250, required=False)
    merchant_identifier = serializers.CharField(max_length=250, required=False)
    consents = UserConsentSerializer(many=True, write_only=True, required=False)
    payment_card_hash = serializers.CharField(max_length=250, required=False)


class LinkSchemeSerializer(SchemeAnswerSerializer):
    consents = UserConsentSerializer(many=True, write_only=True, required=False)

    def validate(self, data):
        # Validate no manual answer
        manual_question_type = self.context["scheme_account_entry"].scheme_account.scheme.manual_question.type
        if manual_question_type in data:
            raise serializers.ValidationError("Manual answer cannot be submitted to this endpoint")

        # Validate credentials existence
        question_types = [answer_type for answer_type, value in data.items()] + [
            manual_question_type,
        ]

        # temporary fix to iceland
        if self.context["scheme_account_entry"].scheme_account.scheme.slug == "iceland-bonus-card":
            return data

        missing_credentials = self.context["scheme_account_entry"].missing_credentials(question_types)
        if missing_credentials:
            raise serializers.ValidationError(
                "All the required credentials have not been submitted: {0}".format(missing_credentials)
            )
        return data


class BalanceSerializer(serializers.Serializer):
    points = serializers.DecimalField(max_digits=30, decimal_places=2, allow_null=True)
    points_label = serializers.CharField(allow_null=True)
    value = serializers.DecimalField(max_digits=30, decimal_places=2, allow_null=True)
    value_label = serializers.CharField(allow_null=True)
    balance = serializers.DecimalField(max_digits=30, decimal_places=2, allow_null=True)
    reward_tier = serializers.IntegerField(allow_null=False)
    is_stale = serializers.BooleanField()


class ReadSchemeAccountAnswerSerializer(serializers.ModelSerializer):
    answer = serializers.CharField(source="clean_answer", read_only=True)

    class Meta:
        model = SchemeAccountCredentialAnswer


class GetSchemeAccountSerializer(serializers.ModelSerializer):
    scheme = SchemeSerializerNoQuestions(read_only=True)
    display_status = serializers.SerializerMethodField()
    barcode = serializers.ReadOnlyField()
    card_label = serializers.ReadOnlyField()
    images = serializers.SerializerMethodField()

    @staticmethod
    def get_images(scheme_account):
        return get_images_for_scheme_account(scheme_account)

    def get_display_status(self, scheme_account):
        user = self.context["request"].user
        entry = SchemeAccountEntry.objects.get(scheme_account=scheme_account, user=user)
        return entry.display_status

    class Meta:
        model = SchemeAccount
        exclude = ("updated", "is_deleted", "balances", "user_set")
        read_only_fields = ("status",)


class QuerySchemeAccountSerializer(serializers.ModelSerializer):
    scheme = SchemeSerializerNoQuestions()
    status_name = serializers.ReadOnlyField()
    barcode = serializers.ReadOnlyField()
    card_label = serializers.ReadOnlyField()
    images = serializers.SerializerMethodField()

    @staticmethod
    def get_images(scheme_account):
        return get_images_for_scheme_account(scheme_account)

    class Meta:
        model = SchemeAccount
        fields = "__all__"


class ReferenceImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchemeImage
        fields = (
            "image",
            "scheme",
        )


class StatusSerializer(serializers.Serializer):
    status = serializers.IntegerField()
    journey = serializers.CharField()


class SchemeAccountIdsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchemeAccount
        fields = ("id",)


class SchemeAccountCredentialsSerializer(serializers.ModelSerializer):
    credentials = serializers.ReadOnlyField()
    status_name = serializers.ReadOnlyField()
    display_status = serializers.ReadOnlyField()
    scheme = serializers.SlugRelatedField(read_only=True, slug_field="slug")

    class Meta:
        model = SchemeAccount
        fields = ("id", "scheme", "credentials", "status", "status_name", "display_status")


class SchemeAccountStatusSerializer(serializers.Serializer):
    name = serializers.CharField()
    status = serializers.CharField()
    description = serializers.CharField()
    count = serializers.IntegerField()


def add_object_type_to_image_response(data, obj_type):
    new_data = copy(data)
    new_data["object_type"] = obj_type
    return new_data


def get_images_for_scheme_account(scheme_account, serializer_class=SchemeAccountImageSerializer, add_type=True):
    account_images = SchemeAccountImage.objects.filter(scheme_accounts__id=scheme_account.id).exclude(
        image_type_code=Image.TIER
    )
    scheme_images = SchemeImage.objects.filter(scheme=scheme_account.scheme)

    images = []

    for image in account_images:
        serializer = serializer_class(image)

        if add_type:
            images.append(add_object_type_to_image_response(serializer.data, "scheme_account_image"))
        else:
            images.append(serializer.data)

    for image in scheme_images:
        account_image = account_images.filter(image_type_code=image.image_type_code).first()

        if not account_image:
            # we have to turn the SchemeImage instance into a SchemeAccountImage
            account_image = SchemeAccountImage(
                id=image.id,
                image_type_code=image.image_type_code,
                size_code=image.size_code,
                image=image.image,
                strap_line=image.strap_line,
                description=image.description,
                url=image.url,
                call_to_action=image.call_to_action,
                order=image.order,
                created=image.created,
                reward_tier=image.reward_tier,
            )
            serializer = serializer_class(account_image)

            if add_type:
                images.append(add_object_type_to_image_response(serializer.data, "scheme_image"))
            else:
                images.append(serializer.data)

    return images


class DonorSchemeInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Scheme
        fields = ("name", "point_name", "id")


class HostSchemeInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Scheme
        fields = ("name", "point_name", "id")


class DonorSchemeSerializer(serializers.ModelSerializer):
    donor_scheme = DonorSchemeInfoSerializer()
    host_scheme = HostSchemeInfoSerializer()

    class Meta:
        model = Exchange
        fields = (
            "donor_scheme",
            "host_scheme",
            "exchange_rate_donor",
            "exchange_rate_host",
            "transfer_min",
            "transfer_max",
            "transfer_multiple",
            "tip_in_url",
            "info_url",
        )


class DonorSchemeAccountSerializer(serializers.Serializer):
    donor_scheme = DonorSchemeInfoSerializer()
    host_scheme = HostSchemeInfoSerializer()
    exchange_rate_donor = serializers.IntegerField()
    exchange_rate_host = serializers.IntegerField()

    transfer_min = serializers.DecimalField(decimal_places=2, max_digits=12)
    transfer_max = serializers.DecimalField(decimal_places=2, max_digits=12)
    transfer_multiple = serializers.DecimalField(decimal_places=2, max_digits=12)

    tip_in_url = serializers.URLField()
    info_url = serializers.URLField()

    scheme_account_id = serializers.IntegerField()


class IdentifyCardSerializer(serializers.Serializer):
    scheme_id = serializers.IntegerField()


class JoinSerializer(SchemeAnswerSerializer):
    save_user_information = serializers.BooleanField(required=True)
    order = serializers.IntegerField(required=True)
    consents = UserConsentSerializer(many=True, write_only=True, required=False)

    def validate(self, data):
        scheme = self.context["scheme"]
        user_id = self.context["user"]
        if isinstance(user_id, CustomUser):
            user_id = user_id.id

        # Validate scheme account for this doesn't already exist
        exclude_status_list = AccountLinkStatus.join_action_required() + [
            AccountLinkStatus.JOIN_ASYNC_IN_PROGRESS,
            AccountLinkStatus.REGISTRATION_ASYNC_IN_PROGRESS,
        ]
        scheme_account_entries = SchemeAccountEntry.objects.filter(
            user_id=user_id, scheme_account__scheme=scheme
        ).exclude(link_status__in=exclude_status_list)

        if scheme_account_entries.exists():
            raise serializers.ValidationError("You already have an account for this scheme: '{0}'".format(scheme))

        required_question_types = [question.type for question in scheme.join_questions if question.required]

        # Validate scheme join questions
        if not required_question_types:
            raise serializers.ValidationError("No join questions found for scheme: {}".format(scheme.slug))

        # Validate all link questions are included in the required join questions
        scheme_link_question_types = [question.type for question in scheme.link_questions]
        if not set(scheme_link_question_types).issubset(required_question_types):
            raise serializers.ValidationError(
                'Please convert all "Link" only credential questions ' 'to "Join & Link" for scheme: {}'.format(scheme)
            )

        return self._validate_join_questions(scheme, data)

    def _validate_join_questions(self, scheme, data):
        request_join_question_types = data.keys()
        data["credentials"] = {}

        for question in scheme.join_questions:
            question_type = question.type
            if question_type in request_join_question_types:
                data["credentials"][question_type] = str(data[question_type])
            else:
                if question.required:
                    self.raise_missing_field_error(question_type)

        return data

    @staticmethod
    def raise_missing_field_error(missing_field):
        raise serializers.ValidationError("{} field required".format(missing_field))


class UbiquityJoinSerializer(JoinSerializer):
    save_user_information = serializers.BooleanField(required=False)
    order = serializers.IntegerField(required=False)

    def validate(self, data):
        scheme = self.context["scheme"]
        return self._validate_join_questions(scheme, data)


class DeleteCredentialSerializer(serializers.Serializer):
    all = serializers.BooleanField(default=False)
    keep_card_number = serializers.BooleanField(default=False)
    property_list = serializers.ListField(default=[])
    type_list = serializers.ListField(default=[])


class UpdateCredentialSerializer(SchemeAnswerSerializer):
    def validate(self, credentials):
        scheme_account_entry = self.context["scheme_account_entry"]
        questions = self.context["questions"]

        # Validate all credential types
        scheme_fields = [question.type for question in questions]
        unknown = set(self.initial_data) - set(scheme_fields)
        if "consents" in unknown:
            unknown.remove("consents")
        if unknown:
            raise serializers.ValidationError("field(s) not found for scheme: {}".format(", ".join(unknown)))

        self._validate_existing_main_answer(
            credentials, questions, scheme_account_entry, self.context["allow_existing_main_answer"]
        )

        return credentials

    @staticmethod
    def _build_q_objects(query_args) -> Q:
        # filter with OR conditions with each main credential to check for existing scheme accounts
        q_objs = Q()
        for key, val in query_args.items():
            if key not in CASE_SENSITIVE_CREDENTIALS:
                val = val.lower()

            if key in [CARD_NUMBER, BARCODE, MERCHANT_IDENTIFIER]:
                q_objs |= Q(**{key: val})
            else:
                q_objs |= Q(alt_main_answer=val)

        return q_objs

    def _validate_existing_main_answer(
        self,
        credentials: dict,
        questions: dict,
        scheme_account_entry: "SchemeAccountEntry",
        allow_existing_main_answer: bool,
    ) -> None:
        main_question_types = {question.type for question in questions if question.is_main_question}

        query_args = {
            answer_type: credentials[answer_type] for answer_type in credentials if answer_type in main_question_types
        }

        scheme_account = scheme_account_entry.scheme_account

        if query_args:
            q_objs = self._build_q_objects(query_args)

            existing_accounts = (
                SchemeAccount.objects.filter(q_objs, scheme=scheme_account.scheme)
                .exclude(id=scheme_account.id)
                .values_list("id")
                .all()
            )

            if len(existing_accounts) == 1 and not allow_existing_main_answer:
                scheme_account_entry.set_link_status(AccountLinkStatus.ACCOUNT_ALREADY_EXISTS)
                logger.error(
                    "Merchant attempt to update a key credential of an account to that of an existing account - "
                    f"Prevented update of {query_args} for Scheme Account (id={scheme_account.id}) - "
                    f"Conflicting Scheme Account (id={existing_accounts[0]})"
                )
                raise serializers.ValidationError("An account already exists with the given credentials")

            elif len(existing_accounts) > 1:
                logger.error(
                    "More than one account found with the same main credential. "
                    "One of the following credentials are the same for scheme account ids "
                    f"{[acc[0] for acc in existing_accounts]}: {query_args.keys()}"
                )
                scheme_account_entry.set_link_status(AccountLinkStatus.ACCOUNT_ALREADY_EXISTS)
                raise serializers.ValidationError("An account already exists with the given credentials")


class UpdateUserConsentSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserConsent
        fields = ("status",)

    def validate_status(self, value):
        if self.instance and self.instance.status == ConsentStatus.SUCCESS:
            raise serializers.ValidationError("Cannot update the consent as it is already in a Success state.")

        return ConsentStatus(int(value))
