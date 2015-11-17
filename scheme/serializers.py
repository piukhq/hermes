from rest_framework import serializers
from scheme.models import Scheme, SchemeAccount, SchemeCredentialQuestion, SchemeImage, SchemeAccountCredentialAnswer


class SchemeImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchemeImage
        exclude = ('scheme',)


class SchemeQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchemeCredentialQuestion
        exclude = ('scheme',)


class SchemeSerializer(serializers.ModelSerializer):
    images = SchemeImageSerializer(many=True, read_only=True)
    questions = SchemeQuestionSerializer(many=True, read_only=True)

    class Meta:
        model = Scheme


class SchemeSerializerNoQuestions(serializers.ModelSerializer):
    is_barcode = serializers.ReadOnlyField()

    class Meta:
        model = Scheme


class LinkSchemeSerializer(serializers.Serializer):
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

    def validate(self, data):
        # Validate scheme account
        try:
            scheme_account = SchemeAccount.objects.get(id=self.context['pk'])
        except SchemeAccount.DoesNotExist:
            raise serializers.ValidationError("Scheme account '{0}' does not exist".format(self.context['pk']))
        data['scheme_account'] = scheme_account

        # Validate no Primary answer
        primary_question_type = scheme_account.scheme.primary_question.type
        if primary_question_type in data:
            raise serializers.ValidationError("Primary answer cannot be submitted to this endpoint")

        # Validate credentials existence
        question_types = [answer_type for answer_type, value in data.items()] + [primary_question_type, ]
        missing_credentials = scheme_account.missing_credentials(question_types)
        if missing_credentials:
            raise serializers.ValidationError(
                "All the required credentials have not been submitted: {0}".format(missing_credentials))
        return data


class SchemeAccountSerializer(serializers.Serializer):
    order = serializers.IntegerField(default=0, required=False)
    primary_answer = serializers.CharField()

    @staticmethod
    def check_unique_scheme(user, scheme):
        scheme_accounts = SchemeAccount.active_objects.filter(user=user, scheme=scheme).exists()
        if scheme_accounts:
            raise serializers.ValidationError("You already have an account for this scheme: '{0}'".format(scheme))


class CreateSchemeAccountSerializer(SchemeAccountSerializer):
    scheme = serializers.IntegerField()
    id = serializers.IntegerField(read_only=True)
    primary_answer_type = serializers.CharField(read_only=True)

    def validate(self, data):
        try:
            scheme = Scheme.objects.get(pk=data['scheme'])
            data['primary_answer_type'] = scheme.primary_question.type
        except Scheme.DoesNotExist:
            raise serializers.ValidationError("Scheme '{0}' does not exist".format(data['scheme']))

        self.check_unique_scheme(self._context['request'].user, scheme)
        return data


class UpdateSchemeAccountSerializer(SchemeAccountSerializer):
    primary_answer = serializers.CharField(required=False)


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
    primary_answer_id = serializers.IntegerField()
    scheme = SchemeSerializerNoQuestions(read_only=True)
    action_status = serializers.ReadOnlyField()
    answers = ReadSchemeAccountAnswerSerializer(many=True, read_only=True)

    class Meta:
        model = SchemeAccount
        exclude = ('updated',)
        read_only_fields = ('status', )


class ListSchemeAccountSerializer(serializers.ModelSerializer):
    scheme = SchemeSerializerNoQuestions()
    primary_answer = ReadSchemeAccountAnswerSerializer(read_only=True)
    status_name = serializers.ReadOnlyField()

    class Meta:
        model = SchemeAccount
        fields = ('id', 'scheme', 'status', 'order', 'created', 'primary_answer', 'action_status', 'status_name')


class StatusSerializer(serializers.Serializer):
    status = serializers.IntegerField()


class SchemeAccountIdsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchemeAccount
        fields = ('id', )


class SchemeAccountCredentialsSerializer(serializers.ModelSerializer):
    credentials = serializers.ReadOnlyField()
    scheme = serializers.SlugRelatedField(read_only=True, slug_field='slug')

    class Meta:
        model = SchemeAccount
        fields = ('id', 'scheme', 'credentials', 'user', 'status')


class SchemeAccountStatusSerializer(serializers.Serializer):
    name = serializers.CharField()
    status = serializers.CharField()
    description = serializers.CharField()
    count = serializers.IntegerField()


class SchemeAccountSummarySerializer(serializers.Serializer):
    scheme_id = serializers.IntegerField()
    statuses = SchemeAccountStatusSerializer(many=True, read_only=True)
