import logging
from typing import TYPE_CHECKING

from rest_framework import serializers

from ubiquity.versioning.base import serializers as base_serializers
from ubiquity.versioning.v1_2 import serializers as v1_2_serializers

if TYPE_CHECKING:
    from scheme.models import Scheme

logger = logging.getLogger(__name__)

ServiceConsentSerializer = v1_2_serializers.ServiceConsentSerializer
PaymentCardSerializer = v1_2_serializers.PaymentCardSerializer
TransactionSerializer = v1_2_serializers.TransactionSerializer
PaymentCardTranslationSerializer = v1_2_serializers.PaymentCardTranslationSerializer
MembershipCardSerializer = v1_2_serializers.MembershipCardSerializer


class MembershipPlanSerializer(v1_2_serializers.MembershipPlanSerializer):
    class ImageSerializer(base_serializers.UbiquityImageSerializer):
        dark_mode_url = serializers.ImageField(source='dark_mode_image', required=False)

    def to_representation(self, instance: 'Scheme') -> dict:
        plan = super().to_representation(instance)
        images = instance.images.all()

        plan["images"] = self.ImageSerializer(images, many=True).data
        plan["card"]["secondary_colour"] = instance.secondary_colour

        return plan
