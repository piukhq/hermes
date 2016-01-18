from rest_framework import serializers

from scheme.credentials import CREDENTIAL_TYPES
from scheme.models import Scheme, SchemeAccount, SchemeCredentialQuestion, SchemeImage, SchemeAccountCredentialAnswer


class SchemeImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchemeImage
        exclude = ('scheme',)


class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchemeCredentialQuestion
        exclude = ('scheme',)


class SchemeSerializer(serializers.ModelSerializer):
    images = SchemeImageSerializer(many=True, read_only=True)
    link_questions = serializers.SerializerMethodField()
    manual_question = QuestionSerializer(read_only=True)
    scan_question = QuestionSerializer(read_only=True)

    class Meta:
        model = Scheme
        exclude = ('card_number_prefix', 'card_number_regex', 'barcode_regex', 'barcode_prefix')

    def get_link_questions(self, obj):
        serializer = QuestionSerializer(obj.link_questions, many=True)
        return serializer.data


class SchemeSerializerNoQuestions(serializers.ModelSerializer):
    class Meta:
        model = Scheme


class SchemeAnswerSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=250, required=False)
    card_number = serializers.CharField(max_length=250, required=False)
    barcode = serializers.CharField(max_length=250, required=False)
    password = serializers.CharField(max_length=250, required=False)
    place_of_birth = serializers.CharField(max_length=250, required=False)
    email = serializers.EmailField(max_length=250, required=False)
    postcode = serializers.CharField(max_length=250, required=False)
    memorable_date = serializers.RegexField(r"^[0-9]{2}/[0-9]{2}/[0-9]{4}$", max_length=250, required=False)
    pin = serializers.RegexField(r"^[0-9]+", max_length=250, required=False)
    last_name = serializers.CharField(max_length=250, required=False)
    favourite_place = serializers.CharField(max_length=250, required=False)


class LinkSchemeSerializer(SchemeAnswerSerializer):
    def validate(self, data):
        # Validate no manual answer
        manual_question_type = self.context['scheme_account'].scheme.manual_question.type
        if manual_question_type in data:
            raise serializers.ValidationError("Manual answer cannot be submitted to this endpoint")

        # Validate credentials existence
        question_types = [answer_type for answer_type, value in data.items()] + [manual_question_type, ]
        missing_credentials = self.context['scheme_account'].missing_credentials(question_types)
        if missing_credentials:
            raise serializers.ValidationError(
                "All the required credentials have not been submitted: {0}".format(missing_credentials))
        return data


class CreateSchemeAccountSerializer(SchemeAnswerSerializer):
    scheme = serializers.IntegerField()
    id = serializers.IntegerField(read_only=True)

    def validate(self, data):
        try:
            scheme = Scheme.objects.get(pk=data['scheme'])
        except Scheme.DoesNotExist:
            raise serializers.ValidationError("Scheme '{0}' does not exist".format(data['scheme']))

        scheme_accounts = SchemeAccount.active_objects.filter(
            user=self.context['request'].user, scheme=scheme).exists()
        if scheme_accounts:
            raise serializers.ValidationError("You already have an account for this scheme: '{0}'".format(scheme))

        answer_types = set(dict(data).keys()).intersection(set(dict(CREDENTIAL_TYPES).keys()))
        if len(answer_types) != 1:
            raise serializers.ValidationError("You must submit one scan or manual question answer")

        answer_type = answer_types.pop()
        self.context['answer_type'] = answer_type
        # only allow one credential
        if answer_type not in self.allowed_answers(scheme):
            raise serializers.ValidationError("Your answer type '{0}' is not allowed".format(answer_type))
        return data

    @staticmethod
    def allowed_answers(scheme):
        allowed_types = []
        if scheme.manual_question:
            allowed_types.append(scheme.manual_question.type)
        if scheme.scan_question:
            allowed_types.append(scheme.scan_question.type)
        return allowed_types


class BalanceSerializer(serializers.Serializer):
    points = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True)
    value = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True)
    value_label = serializers.CharField(allow_null=True)
    balance = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True)
    is_stale = serializers.BooleanField()


class ResponseLinkSerializer(serializers.Serializer):
    status = serializers.IntegerField(allow_null=True)
    status_name = serializers.CharField()
    balance = BalanceSerializer(allow_null=True)


class ReadSchemeAccountAnswerSerializer(serializers.ModelSerializer):
    answer = serializers.CharField(source='clean_answer', read_only=True)

    class Meta:
        model = SchemeAccountCredentialAnswer


class GetSchemeAccountSerializer(serializers.ModelSerializer):
    scheme = SchemeSerializerNoQuestions(read_only=True)
    action_status = serializers.ReadOnlyField()
    barcode = serializers.ReadOnlyField()
    card_label = serializers.ReadOnlyField()

    class Meta:
        model = SchemeAccount
        exclude = ('updated', 'is_deleted')
        read_only_fields = ('status', )


class ListSchemeAccountSerializer(serializers.ModelSerializer):
    scheme = SchemeSerializerNoQuestions()
    manual_answer = ReadSchemeAccountAnswerSerializer(read_only=True)
    status_name = serializers.ReadOnlyField()

    class Meta:
        model = SchemeAccount
        fields = ('id', 'scheme', 'status', 'order', 'created', 'manual_answer', 'action_status', 'status_name')


class StatusSerializer(serializers.Serializer):
    status = serializers.IntegerField()


class SchemeAccountIdsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchemeAccount
        fields = ('id', )


class SchemeAccountCredentialsSerializer(serializers.ModelSerializer):
    credentials = serializers.ReadOnlyField()
    status_name = serializers.ReadOnlyField()
    action_status = serializers.ReadOnlyField()
    scheme = serializers.SlugRelatedField(read_only=True, slug_field='slug')

    class Meta:
        model = SchemeAccount
        fields = ('id', 'scheme', 'credentials', 'user', 'status', 'status_name', 'action_status')


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
