import logging
from typing import TYPE_CHECKING

from rest_framework import serializers

from ubiquity.versioning.base import serializers as base_serializers
from ubiquity.versioning.v1_2 import serializers as v1_2_serializers
from ubiquity.reason_codes import get_state_reason_code_and_text

if TYPE_CHECKING:
    from scheme.models import Scheme, SchemeAccount

logger = logging.getLogger(__name__)

ServiceSerializer = v1_2_serializers.ServiceSerializer
PaymentCardSerializer = v1_2_serializers.PaymentCardSerializer
TransactionSerializer = v1_2_serializers.TransactionSerializer
PaymentCardTranslationSerializer = v1_2_serializers.PaymentCardTranslationSerializer
MembershipCardSerializer = v1_2_serializers.MembershipCardSerializer


class UbiquityImageSerializer(base_serializers.UbiquityImageSerializer):
    cta_url = serializers.CharField(source='call_to_action')


class MembershipCardSerializer(base_serializers.MembershipCardSerializer):
    @staticmethod
    def get_translated_status(instance: 'SchemeAccount', status: 'SchemeAccount.STATUSES') -> dict:
        if status in instance.SYSTEM_ACTION_REQUIRED:
            if instance.balances:
                status = instance.ACTIVE
            else:
                status = instance.PENDING

        state, reason_codes, error_text = get_state_reason_code_and_text(status)
        scheme_errors = instance.scheme.schemeoverrideerror_set.all()

        for error in scheme_errors:
            if error.error_code == status:
                error_text = error.message
                break

        return {
            "state": state,
            "reason_codes": reason_codes,
            "error_text": error_text
        }


class MembershipPlanSerializer(v1_2_serializers.MembershipPlanSerializer):
    class ImageSerializer(UbiquityImageSerializer):
        dark_mode_url = serializers.ImageField(source='dark_mode_image', required=False)

    def to_representation(self, instance: 'Scheme') -> dict:
        plan = super().to_representation(instance)
        images = instance.images.all()

        plan["images"] = self.ImageSerializer(images, many=True).data
        plan["card"]["secondary_colour"] = instance.secondary_colour

        return plan
