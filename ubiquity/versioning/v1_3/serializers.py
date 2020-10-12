import logging

from ubiquity.versioning.v1_2 import serializers as v1_2_serializers


logger = logging.getLogger(__name__)

ServiceConsentSerializer = v1_2_serializers.ServiceConsentSerializer
PaymentCardSerializer = v1_2_serializers.PaymentCardSerializer
TransactionSerializer = v1_2_serializers.TransactionSerializer
MembershipCardSerializer = v1_2_serializers.MembershipCardSerializer
PaymentCardTranslationSerializer = v1_2_serializers.PaymentCardTranslationSerializer


class MembershipPlanSerializer(v1_2_serializers.MembershipPlanSerializer):

    def to_representation(self, instance: 'Scheme') -> dict:
        plan = super().to_representation(instance)
        plan["card"]["secondary_colour"] = instance.secondary_colour
        return plan
