from rest_framework import serializers
from scheme.models import Scheme, SchemeAccount, SchemeAccountSecurityQuestion

#TODO: TRY Model serializers

class SchemeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Scheme
        #fields = ('id', 'title', 'code', 'linenos', 'language', 'style')

class SchemeAccountSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    card_number = serializers.CharField(max_length=50)
    membership_number = serializers.CharField(max_length=50)
    password = serializers.CharField(max_length=30)

    def create(self, validated_data):
        return SchemeAccount.objects.create(**validated_data)

    def update(self, instance, validated_data):
        return instance


class SchemeAccountSecurityQuestionSerializer(serializers.Serializer):
    question = serializers.CharField(max_length=250)
    answer = serializers.CharField(max_length=250)

    def create(self, validated_data):
        return SchemeAccountSecurityQuestion.objects.create(**validated_data)

    def update(self, instance, validated_data):
        return instance
