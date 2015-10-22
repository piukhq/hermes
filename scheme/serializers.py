from rest_framework import serializers
from scheme.models import Scheme, SchemeAccount, SchemeAccountCredentialAnswer, SchemeCredentialQuestion, SchemeImage


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


class CreateSchemeAccountSerializer(serializers.ModelSerializer):
    primary_answer = SchemeAccountAnswerSerializer(read_only=True)

    class Meta:
        model = SchemeAccount
        exclude = ('updated', )
        read_only_fields = ('status', )


class UpdateSchemeAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchemeAccount
        exclude = ('updated', 'status')
        read_only_fields = ('user', 'scheme')


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
        # exclude = ('updated', )


class StatusSerializer(serializers.Serializer):
    status = serializers.IntegerField()


class ActiveSchemeAccountAccountsSerializer(serializers.ModelSerializer):
    credentials = serializers.ReadOnlyField()
    scheme = serializers.SlugRelatedField(read_only=True, slug_field='slug')

    class Meta:
        model = SchemeAccount
        fields = ('id', 'scheme', 'credentials', 'user')
