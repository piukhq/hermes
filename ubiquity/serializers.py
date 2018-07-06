import arrow
from arrow.parser import ParserError
from rest_framework import serializers

from ubiquity.models import ServiceConsent
from user.models import CustomUser


class ServiceConsentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceConsent
        fields = '__all__'

    timestamp = serializers.IntegerField()

    @staticmethod
    def validate_user(user):
        try:
            user_obj = CustomUser.objects.get(pk=user)
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError("User {} not found.".format(user))

        return user_obj

    @staticmethod
    def validate_timestamp(timestamp):
        try:
            datetime = arrow.get(timestamp).datetime
        except ParserError:
            raise serializers.ValidationError('timestamp field is not a timestamp.')

        return datetime
