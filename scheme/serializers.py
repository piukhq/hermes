from rest_framework import serializers
from scheme.models import Scheme, SchemeAccount, SchemeAccountSecurityQuestion


class SchemeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Scheme


class SchemeAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchemeAccount
        exclude = ('updated', 'status')



class SchemeAccountSecurityQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchemeAccountSecurityQuestion
        exclude = ('user', )
