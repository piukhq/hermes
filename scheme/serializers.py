from rest_framework import serializers
from scheme.models import Scheme, SchemeAccount, SchemeAccountCredentialAnswer, SchemeCredentialQuestion


class SchemeQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchemeCredentialQuestion
        exclude = ('id', 'scheme')


class SchemeSerializer(serializers.ModelSerializer):
    questions = SchemeQuestionSerializer(many=True, read_only=True)

    class Meta:
        model = Scheme


class SchemeSerializerNoQuestions(serializers.ModelSerializer):
    class Meta:
        model = Scheme



class SchemeAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchemeAccount
        exclude = ('updated', 'status')


class UpdateSchemeAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchemeAccount
        exclude = ('updated', 'status')
        read_only_fields = ('user', 'scheme')


class ListSchemeAccountSerializer(SchemeAccountSerializer):
    scheme = SchemeSerializerNoQuestions()
    primary_answer = serializers.CharField(read_only=True)


class SchemeAccountAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchemeAccountCredentialAnswer
