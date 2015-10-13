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
    primary_answer = SchemeAccountAnswerSerializer(read_only=True)
    scheme = SchemeSerializerNoQuestions(read_only=True)

    class Meta:
        model = SchemeAccount
        exclude = ('updated', )
        read_only_fields = ('status', )


class ListSchemeAccountSerializer(serializers.ModelSerializer):
    scheme = SchemeSerializerNoQuestions()

    class Meta:
        model = SchemeAccount
        exclude = ('updated', )


