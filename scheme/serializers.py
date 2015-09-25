from rest_framework import serializers
from scheme.models import Scheme, SchemeAccount, SchemeAccountCredentialAnswer


class SchemeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Scheme


class SchemeAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchemeAccount
        exclude = ('updated', 'status')


class SchemeAccountAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchemeAccountCredentialAnswer
