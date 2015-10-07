from rest_framework import serializers
from scheme.models import Scheme, SchemeAccount, SchemeAccountCredentialAnswer, SchemeCredentialQuestion, SchemeImage


class SchemeImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchemeImage
        exclude = ('id', 'scheme')

class SchemeQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchemeCredentialQuestion
        exclude = ('id', 'scheme')


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


class SchemeAccountSerializer(serializers.ModelSerializer):
    primary_answer = SchemeAccountAnswerSerializer(read_only=True)

    class Meta:
        model = SchemeAccount
        exclude = ('updated', )
        read_only_fields = ('status')



class UpdateSchemeAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchemeAccount
        exclude = ('updated', 'status')
        read_only_fields = ('user', 'scheme')


class ListSchemeAccountSerializer(serializers.ModelSerializer):
    scheme = SchemeSerializerNoQuestions()

    class Meta:
        model = SchemeAccount
        exclude = ('updated', )


