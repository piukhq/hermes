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


class SchemeAccountAnswerSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=250, required=False)
    card_number = serializers.CharField(max_length=250, required=False)
    barcode = serializers.CharField(max_length=250, required=False)
    password = serializers.CharField(max_length=250, required=False)
    place_of_birth = serializers.CharField(max_length=250, required=False)
    email = serializers.CharField(max_length=250, required=False)
    postcode = serializers.CharField(max_length=250, required=False)
    memorable_date = serializers.CharField(max_length=250, required=False)
    pin = serializers.CharField(max_length=250, required=False)
    last_name = serializers.CharField(max_length=250, required=False)

    def validate(self, data):
        try:
            scheme_account = SchemeAccount.objects.get(id=self.context['pk'])
        except SchemeAccount.DoesNotExist:
            raise serializers.ValidationError("Scheme account '{0}' does not exist".format(self.context['pk']))

        primary_question_type = scheme_account.scheme.primary_question.type

        if primary_question_type in data:
            raise serializers.ValidationError("Primary answer cannot be submitted to this endpoint")

        question_types = [answer_type for answer_type, value in data.items()] + [primary_question_type, ]
        if not scheme_account.valid_credentials(question_types):
            raise serializers.ValidationError("All the required credentials have not been submitted")
        data['scheme_account'] = scheme_account
        return data


class SchemeAccountSerializer(serializers.Serializer):
    order = serializers.IntegerField(default=0, required=False)
    primary_answer = serializers.CharField()

    @staticmethod
    def check_primary_answer(user, scheme, new_primary_answer):
        # Loop though users accounts of same scheme and make sure they don't use the same primary answer
        scheme_accounts = SchemeAccount.active_objects.filter(user=user, scheme=scheme)
        for scheme_account in scheme_accounts:
            primary_answer = scheme_account.primary_answer
            if primary_answer and primary_answer.answer == new_primary_answer:
                raise serializers.ValidationError("You already have an account with the primary answer: '{0}'".format(
                   new_primary_answer))


class CreateSchemeAccountSerializer(SchemeAccountSerializer):
    scheme = serializers.IntegerField()

    def validate(self, data):
        try:
            scheme = Scheme.objects.get(pk=data['scheme'])
            data['primary_answer_type'] = scheme.primary_question.type
        except Scheme.DoesNotExist:
            raise serializers.ValidationError("Scheme '{0}' does not exist".format(data['scheme']))

        self.check_primary_answer(self._context['request'].user, scheme, data['primary_answer'])
        return data


class UpdateSchemeAccountSerializer(SchemeAccountSerializer):
    primary_answer = serializers.CharField(required=False)

    def validate_primary_answer(self, value):
        self.check_primary_answer(self.context['request'].user, self._context['view'].context['scheme'], value)
        return value


class ResponseAgentSerializer(serializers.Serializer):
    points = serializers.IntegerField(allow_null=True)
    status = serializers.IntegerField()


class ReadSchemeAccountAnswerSerializer(serializers.ModelSerializer):
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

    class Meta:
        model = SchemeAccount
        fields = ('id', 'scheme', 'status', 'order', 'created', 'primary_answer', 'action_status')


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
