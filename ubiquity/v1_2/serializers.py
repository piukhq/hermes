from ubiquity.base import serializers as base_serializers

MembershipPlanSerializer = base_serializers.MembershipPlanSerializer
MembershipCardSerializer = base_serializers.MembershipCardSerializer
PaymentCardSerializer = base_serializers.PaymentCardSerializer
TransactionsSerializer = base_serializers.TransactionsSerializer


class ServiceConsentSerializer(base_serializers.ServiceConsentSerializer):
    def to_representation(self, instance):
        response = {'email': instance.user.email, 'timestamp': int(instance.timestamp.timestamp())}
        if self._is_valid(instance.latitude) and self._is_valid(instance.longitude):
            response.update({'latitude': instance.latitude, 'longitude': instance.longitude})
        return {
            'consent': response,
            'version': '1.2'
        }
