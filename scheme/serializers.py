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


class SchemeAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchemeAccount
        exclude = ('updated', 'status')


class SchemeAccountAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchemeAccountCredentialAnswer
