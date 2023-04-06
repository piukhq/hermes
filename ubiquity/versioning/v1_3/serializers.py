import logging
from typing import TYPE_CHECKING

from rest_framework import serializers

from ubiquity.models import AccountLinkStatus, SchemeAccountEntry
from ubiquity.reason_codes import get_state_reason_code_and_text
from ubiquity.versioning.base import serializers as base_serializers
from ubiquity.versioning.v1_2 import serializers as v1_2_serializers

if TYPE_CHECKING:
    from scheme.models import Scheme

logger = logging.getLogger(__name__)

ServiceSerializer = v1_2_serializers.ServiceSerializer
PaymentCardSerializer = v1_2_serializers.PaymentCardSerializer
TransactionSerializer = v1_2_serializers.TransactionSerializer
PaymentCardTranslationSerializer = v1_2_serializers.PaymentCardTranslationSerializer


class UbiquityImageSerializer(base_serializers.UbiquityImageSerializer):
    cta_url = serializers.CharField(source="call_to_action")


class MembershipCardSerializer(base_serializers.MembershipCardSerializer):
    @staticmethod
    def get_translated_status(scheme_account_entry: "SchemeAccountEntry") -> dict:
        status = display_status = scheme_account_entry.link_status

        if status in AccountLinkStatus.system_action_required():
            if scheme_account_entry.scheme_account.balances:
                display_status = AccountLinkStatus.ACTIVE
            else:
                display_status = AccountLinkStatus.PENDING

        state, reason_codes, error_text = get_state_reason_code_and_text(display_status)
        scheme_errors = scheme_account_entry.scheme_account.scheme.schemeoverrideerror_set.all()

        for error in scheme_errors:
            if error.error_code == status:
                error_text = error.message
                reason_codes = [error.reason_code]
                break

        return {"state": state, "reason_codes": reason_codes, "error_text": error_text}


class MembershipPlanSerializer(v1_2_serializers.MembershipPlanSerializer):
    class ImageSerializer(UbiquityImageSerializer):
        dark_mode_url = serializers.SerializerMethodField()

        def get_dark_mode_url(self, obj):
            return self.image_url(obj.dark_mode_image)

    image_serializer_class = ImageSerializer

    def to_representation(self, instance: "Scheme") -> dict:
        plan = super().to_representation(instance)
        plan["card"]["secondary_colour"] = instance.secondary_colour
        plan["slug"] = instance.slug
        if instance.go_live:
            plan["go_live"] = instance.go_live.isoformat()
        return plan
