from rest_framework import serializers
from scheme.models import Scheme, SchemeAccount, SchemeAccountCredentialAnswer, SchemeCredentialQuestion, SchemeImage
from scheme.credentials import CREDENTIAL_TYPES

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


class SchemeAccountAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchemeAccountCredentialAnswer


class CreateSchemeAccountSerializer(serializers.Serializer):
    scheme = serializers.IntegerField()
    order = serializers.IntegerField(default=0)
    primary_answer = serializers.CharField()

    def validate(self, data):
        try:
            scheme = Scheme.objects.get(pk=data['scheme'])
            data['primary_answer_type'] = scheme.primary_question.type
        except Scheme.DoesNotExist:
            raise serializers.ValidationError("Scheme '{0}' does not exist".format(data['scheme']))

        # Loop though users accounts of same scheme and make sure they don't use the same primary answer
        for scheme_account in SchemeAccount.active_objects.filter(user=self._context['request'].user, scheme=scheme):
            primary_answer = scheme_account.primary_answer
            if primary_answer and primary_answer.answer == data['primary_answer']:
                raise serializers.ValidationError("You already have an account with the primary answer: '{0}'".format(
                    data['primary_answer']))
        return data


class CreateSchemeAccountSerializerResponse(CreateSchemeAccountSerializer):
    id = serializers.IntegerField()
    primary_answer_type = serializers.CharField()

    def validate(self, data):
        """
        Check that the primary answer type has been supplied.
        """
        if not data['primary_answer_type'] in dict(CREDENTIAL_TYPES):
            raise serializers.ValidationError("The primary answer type is incorrect: '{0}'".format(
                    data['primary_answer_type']))
        return data


class UpdateSchemeAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchemeAccount
        exclude = ('updated', 'status', 'user')
        read_only_fields = ('scheme', )


class GetSchemeAccountSerializer(serializers.ModelSerializer):
    primary_answer_id = serializers.IntegerField()
    scheme = SchemeSerializerNoQuestions(read_only=True)
    action_status = serializers.ReadOnlyField()
    answers = SchemeAccountAnswerSerializer(many=True, read_only=True)

    class Meta:
        model = SchemeAccount
        exclude = ('updated',)
        read_only_fields = ('status', )


class ListSchemeAccountSerializer(serializers.ModelSerializer):
    scheme = SchemeSerializerNoQuestions()
    primary_answer = SchemeAccountAnswerSerializer(read_only=True)

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
