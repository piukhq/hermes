from rest_framework import serializers

from ubiquity.models import ServiceConsent
from user.models import CustomUser


class ServiceConsentSerilizer(serializers.ModelSerializer):
    class Meta:
        model = ServiceConsent
        fields = '__all__'

    def validate_user(self, user):
        if not isinstance(user, CustomUser):
            raise serializers.ValidationError("{} is not a valid user.".format(user))

        return user

    def validate_timestamp(self, timestamp):
        return timestamp

    def save(self, **kwargs):
        pass
