import arrow
from arrow.parser import ParserError
from rest_framework import serializers

from payment_card.serializers import PaymentCardAccountSerializer
from scheme.serializers import GetSchemeAccountSerializer, ListSchemeAccountSerializer
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


class PaymentCardConsentSerializer(serializers.Serializer):
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    timestamp = serializers.IntegerField()


class PaymentCardSerializer(PaymentCardAccountSerializer):
    class Meta(PaymentCardAccountSerializer.Meta):
        exclude = ('token', 'psp_token', 'user_set')


class BalanceSerializer(serializers.Serializer):
    points = serializers.FloatField()
    value = serializers.FloatField()
    value_label = serializers.CharField()
    points_label = serializers.CharField()
    reward_tier = serializers.IntegerField()


class MembershipCardSerializer(GetSchemeAccountSerializer):
    balance = BalanceSerializer(read_only=True)

    class Meta(GetSchemeAccountSerializer.Meta):
        exclude = ('updated', 'is_deleted')


class ListMembershipCardSerializer(ListSchemeAccountSerializer):
    balance = BalanceSerializer(read_only=True)

    class Meta(ListSchemeAccountSerializer.Meta):
        fields = ListSchemeAccountSerializer.Meta.fields + ('balance',)
