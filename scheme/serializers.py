from copy import copy

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers

from common.models import Image
from scheme.credentials import credential_types_set
from scheme.models import (Consent, ConsentStatus, Control, Exchange, Scheme, SchemeAccount,
                           SchemeAccountCredentialAnswer, SchemeAccountImage, SchemeCredentialQuestion, SchemeImage,
                           UserConsent)
from ubiquity.models import PaymentCardAccountEntry
from user.models import CustomUser


class SchemeImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchemeImage
        exclude = ('scheme',)


class SchemeAccountImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchemeAccountImage
        fields = '__all__'


class QuestionSerializer(serializers.ModelSerializer):
    required = serializers.BooleanField()
    question_choices = serializers.ListField()

    class Meta:
        model = SchemeCredentialQuestion
        exclude = ('scheme', 'manual_question', 'scan_question', 'one_question_link', 'options')


class ConsentsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Consent
        exclude = ('is_enabled', 'scheme', 'created_on', 'modified_on')


class ControlSerializer(serializers.ModelSerializer):
    class Meta:
        model = Control
        exclude = ('id', 'scheme')


class TransactionHeaderSerializer(serializers.Serializer):
    """ This serializer is required to convert a list of header titles into a
    form which the front end requires ie a list of key pairs where the key is
    a keyword "name" and the value is the header title.
    This is a departure from rest mapping to the model and was agreed with Paul Batty.
    Any serializer requiring transaction headers in this form should use
    transaction_headers = TransactionHeaderSerializer() otherwise transaction_headers will
    be represented by a simple list of headers.
    """

    @staticmethod
    def to_representation(obj):
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
    is_active = serializers.BooleanField()

    class Meta:
        model = Scheme
        exclude = ('card_number_prefix', 'card_number_regex', 'barcode_regex', 'barcode_prefix')

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
    is_active = serializers.BooleanField()

    class Meta:
        model = Scheme
        exclude = ('card_number_prefix', 'card_number_regex', 'barcode_regex', 'barcode_prefix')


class UserConsentSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    value = serializers.BooleanField()

    @staticmethod
    def get_user_consents(scheme_account, consents, user):
        """
        Returns UserConsent instances from the data sent by the frontend (Consent id and a value of true/false.)
        These are not yet saved to the database.
        """
        user_consents = []
        for consent in consents:
            value = consent['value']
            consent = get_object_or_404(Consent, pk=consent['id'])

            user_consent = UserConsent(scheme_account=scheme_account, value=value, slug=consent.slug,
                                       user=user, created_on=timezone.now(),
                                       scheme=scheme_account.scheme)

            serializer = ConsentsSerializer(consent)
            user_consent.metadata = serializer.data
            user_consent.metadata.update({
                'user_email': user.email,
                'scheme_slug': scheme_account.scheme.slug
            })

            user_consents.append(user_consent)

        return user_consents

    @staticmethod
    def validate_consents(user_consents, scheme, journey_type):
        consents = Consent.objects.filter(scheme=scheme, journey=journey_type, check_box=True)

        # Validate correct number of user_consents provided
        expected_consents_set = {consent.slug for consent in consents}

        if len(expected_consents_set) != len(user_consents):
            raise serializers.ValidationError({
                "message": "Incorrect number of consents provided for this scheme and journey type.",
                "code": serializers.ValidationError.status_code
            })

        # Validate slugs match those expected for slug + journey
        actual_consents_set = {user_consent.slug for user_consent in user_consents}

        if expected_consents_set.symmetric_difference(actual_consents_set):
            raise serializers.ValidationError({
                "message": "Unexpected or missing user consents for '{0}' request - scheme id '{1}'".format(
                    Consent.journeys[journey_type][1],
                    scheme
                ),
                "code": serializers.ValidationError.status_code
            })

        # Validate that the user consents for all required consents have a value of True
        invalid_consents = [{'consent_id': consent.metadata['id'], 'slug': consent.slug} for consent in user_consents
                            if consent.metadata['required'] is True
                            and consent.value is False]

        if invalid_consents:
            raise serializers.ValidationError({
                "message": "The following consents require a value of True: {}".format(invalid_consents),
                "code": serializers.ValidationError.status_code
            })

        return user_consents


class SchemeAnswerSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=250, required=False)
    card_number = serializers.CharField(max_length=250, required=False)
    barcode = serializers.CharField(max_length=250, required=False)
    password = serializers.CharField(max_length=250, required=False)
    place_of_birth = serializers.CharField(max_length=250, required=False)
    email = serializers.EmailField(max_length=250, required=False)
    postcode = serializers.CharField(max_length=250, required=False)
    memorable_date = serializers.DateField(input_formats=["%d/%M/%Y"], required=False)
    pin = serializers.RegexField(r"^[0-9]+", max_length=250, required=False)
    title = serializers.CharField(max_length=250, required=False)
    first_name = serializers.CharField(max_length=250, required=False)
    last_name = serializers.CharField(max_length=250, required=False)
    favourite_place = serializers.CharField(max_length=250, required=False)
    date_of_birth = serializers.DateField(input_formats=["%d/%M/%Y"], required=False)
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


class LinkSchemeSerializer(SchemeAnswerSerializer):
    consents = UserConsentSerializer(many=True, write_only=True, required=False)

    def validate(self, data):
        # Validate no manual answer
        manual_question_type = self.context['scheme_account'].scheme.manual_question.type
        if manual_question_type in data:
            raise serializers.ValidationError("Manual answer cannot be submitted to this endpoint")

        # Validate credentials existence
        question_types = [answer_type for answer_type, value in data.items()] + [manual_question_type, ]

        # temporary fix to iceland
        if self.context['scheme_account'].scheme.slug == 'iceland-bonus-card':
            return data

        missing_credentials = self.context['scheme_account'].missing_credentials(question_types)
        if missing_credentials:
            raise serializers.ValidationError(
                "All the required credentials have not been submitted: {0}".format(missing_credentials))
        return data


class CreateSchemeAccountSerializer(SchemeAnswerSerializer):
    scheme = serializers.IntegerField()
    order = serializers.IntegerField()
    id = serializers.IntegerField(read_only=True)
    consents = UserConsentSerializer(many=True, write_only=True, required=False)
    verify_account_exists = True

    def validate(self, data):
        try:
            scheme = Scheme.objects.get(pk=data['scheme'])
        except Scheme.DoesNotExist:
            raise serializers.ValidationError("Scheme '{0}' does not exist".format(data['scheme']))

        answer_types = set(data).intersection(credential_types_set)
        if len(answer_types) != 1:
            raise serializers.ValidationError("You must submit one scan or manual question answer")

        answer_type = answer_types.pop()
        self.context['answer_type'] = answer_type
        # only allow one credential
        if answer_type not in self.allowed_answers(scheme):
            raise serializers.ValidationError("Your answer type '{0}' is not allowed".format(answer_type))

        if self.verify_account_exists:
            self.check_scheme_linked_to_same_payment_card(user_id=self.context['request'].user.id, scheme_id=scheme.id)
            scheme_accounts = SchemeAccount.objects.filter(user_set__id=self.context['request'].user.id,
                                                           scheme=scheme).exclude(status=SchemeAccount.JOIN)
            for sa in scheme_accounts.all():
                if sa.schemeaccountcredentialanswer_set.filter(answer=data[answer_type]).exists():
                    raise serializers.ValidationError("You already added this account for scheme: '{0}'".format(scheme))

        return data

    @staticmethod
    def check_scheme_linked_to_same_payment_card(user_id, scheme_id):
        pca_ids = PaymentCardAccountEntry.objects.values('payment_card_account_id').filter(user_id=user_id).all()
        # todo when the linking of cards is implemented in bink, change this to use PaymentCardSchemeEntry table
        for pca_id in pca_ids:
            filter_query = {
                'payment_card_account_set__id': pca_id['payment_card_account_id'],
                'scheme_account_set__scheme_id': scheme_id
            }
            if CustomUser.objects.values('scheme_account_set__id').filter(**filter_query).count() >= 1:
                raise serializers.ValidationError("An account for this scheme is already associated "
                                                  "with one of the payment cards in your wallet.")

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


class BalanceSerializer(serializers.Serializer):
    points = serializers.DecimalField(max_digits=30, decimal_places=2, allow_null=True)
    points_label = serializers.CharField(allow_null=True)
    value = serializers.DecimalField(max_digits=30, decimal_places=2, allow_null=True)
    value_label = serializers.CharField(allow_null=True)
    balance = serializers.DecimalField(max_digits=30, decimal_places=2, allow_null=True)
    reward_tier = serializers.IntegerField(allow_null=False)
    is_stale = serializers.BooleanField()


class ResponseLinkSerializer(serializers.Serializer):
    status = serializers.IntegerField(allow_null=True)
    status_name = serializers.CharField()
    balance = BalanceSerializer(allow_null=True)
    display_status = serializers.ReadOnlyField()


class ReadSchemeAccountAnswerSerializer(serializers.ModelSerializer):
    answer = serializers.CharField(source='clean_answer', read_only=True)

    class Meta:
        model = SchemeAccountCredentialAnswer


class GetSchemeAccountSerializer(serializers.ModelSerializer):
    scheme = SchemeSerializerNoQuestions(read_only=True)
    display_status = serializers.ReadOnlyField()
    barcode = serializers.ReadOnlyField()
    card_label = serializers.ReadOnlyField()
    images = serializers.SerializerMethodField()

    @staticmethod
    def get_images(scheme_account):
        return get_images_for_scheme_account(scheme_account)

    class Meta:
        model = SchemeAccount
        exclude = ('updated', 'is_deleted', 'balances', 'user_set')
        read_only_fields = ('status',)


class ListSchemeAccountSerializer(serializers.ModelSerializer):
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
        fields = ('id',
                  'scheme',
                  'status',
                  'order',
                  'created',
                  'display_status',
                  'status_name',
                  'barcode',
                  'card_label',
                  'images')


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
        fields = '__all__'


class ReferenceImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchemeImage
        fields = (
            'image',
            'scheme',
        )


class StatusSerializer(serializers.Serializer):
    status = serializers.IntegerField()
    journey = serializers.CharField()


class SchemeAccountIdsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchemeAccount
        fields = ('id',)


class SchemeAccountCredentialsSerializer(serializers.ModelSerializer):
    credentials = serializers.ReadOnlyField()
    status_name = serializers.ReadOnlyField()
    display_status = serializers.ReadOnlyField()
    scheme = serializers.SlugRelatedField(read_only=True, slug_field='slug')

    class Meta:
        model = SchemeAccount
        fields = ('id', 'scheme', 'credentials', 'status', 'status_name', 'display_status')


class SchemeAccountStatusSerializer(serializers.Serializer):
    name = serializers.CharField()
    status = serializers.CharField()
    description = serializers.CharField()
    count = serializers.IntegerField()


class SchemeAccountSummarySerializer(serializers.Serializer):
    scheme_id = serializers.IntegerField()
    statuses = SchemeAccountStatusSerializer(many=True, read_only=True)


class ResponseSchemeAccountAndBalanceSerializer(LinkSchemeSerializer, ResponseLinkSerializer):
    pass


def add_object_type_to_image_response(data, type):
    new_data = copy(data)
    new_data['object_type'] = type
    return new_data


def get_images_for_scheme_account(scheme_account, serializer_class=SchemeAccountImageSerializer, add_type=True):
    account_images = SchemeAccountImage.objects.filter(
        scheme_accounts__id=scheme_account.id
    ).exclude(image_type_code=Image.TIER)
    scheme_images = SchemeImage.objects.filter(scheme=scheme_account.scheme)

    images = []

    for image in account_images:
        serializer = serializer_class(image)

        if add_type:
            images.append(add_object_type_to_image_response(serializer.data, 'scheme_account_image'))
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
                reward_tier=image.reward_tier
            )
            serializer = serializer_class(account_image)

            if add_type:
                images.append(add_object_type_to_image_response(serializer.data, 'scheme_image'))
            else:
                images.append(serializer.data)

    return images


class DonorSchemeInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Scheme
        fields = ('name', 'point_name', 'id')


class HostSchemeInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Scheme
        fields = ('name', 'point_name', 'id')


class DonorSchemeSerializer(serializers.ModelSerializer):
    donor_scheme = DonorSchemeInfoSerializer()
    host_scheme = HostSchemeInfoSerializer()

    class Meta:
        model = Exchange
        fields = ('donor_scheme', 'host_scheme', 'exchange_rate_donor', 'exchange_rate_host',
                  'transfer_min', 'transfer_max', 'transfer_multiple', 'tip_in_url', 'info_url',)


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
    save_user_information = serializers.NullBooleanField(required=True)
    order = serializers.IntegerField(required=True)
    consents = UserConsentSerializer(many=True, write_only=True, required=False)

    def validate(self, data):
        scheme = self.context['scheme']
        user_id = self.context['user']
        if isinstance(user_id, CustomUser):
            user_id = user_id.id

        # Validate scheme account for this doesn't already exist
        scheme_accounts = SchemeAccount.objects.filter(user_set__id=user_id, scheme=scheme) \
            .exclude(status=SchemeAccount.JOIN)

        if scheme_accounts.exists():
            raise serializers.ValidationError("You already have an account for this scheme: '{0}'".format(scheme))

        required_question_types = [
            question.type
            for question in scheme.join_questions
            if question.required
        ]

        # Validate scheme join questions
        if not required_question_types:
            raise serializers.ValidationError("No join questions found for scheme: {}".format(scheme.slug))

        # Validate all link questions are included in the required join questions
        scheme_link_question_types = [question.type for question in scheme.link_questions]
        if not set(scheme_link_question_types).issubset(required_question_types):
            raise serializers.ValidationError("Please convert all \"Link\" only credential questions "
                                              "to \"Join & Link\" for scheme: {}".format(scheme))

        # Validate request join questions
        return self._validate_join_questions(scheme, data)

    def _validate_join_questions(self, scheme, data):
        request_join_question_types = data.keys()
        data['credentials'] = {}
        for question in scheme.join_questions:
            question_type = question.type
            if question_type in request_join_question_types:
                data['credentials'][question_type] = str(data[question_type])

            else:
                if question.required:
                    self.raise_missing_field_error(question_type)

        return data

    @staticmethod
    def raise_missing_field_error(missing_field):
        raise serializers.ValidationError("{} field required".format(missing_field))


class DeleteCredentialSerializer(serializers.Serializer):
    all = serializers.NullBooleanField(default=False)
    property_list = serializers.ListField(default=[])
    type_list = serializers.ListField(default=[])


class UpdateCredentialSerializer(SchemeAnswerSerializer):

    def validate(self, credentials):
        # Validate all credential types
        scheme_fields = [field.type for field in self.context['scheme_account'].scheme.questions.all()]
        unknown = set(self.initial_data) - set(scheme_fields)
        if unknown:
            raise serializers.ValidationError(
                "field(s) not found for scheme: {}".format(", ".join(unknown))
            )

        return credentials


class UpdateUserConsentSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserConsent
        fields = ('status',)

    def validate_status(self, value):
        if self.instance and self.instance.status == ConsentStatus.SUCCESS:
            raise serializers.ValidationError('Cannot update the consent as it is already in a Success state.')

        return ConsentStatus(int(value))
