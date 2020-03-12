from typing import TYPE_CHECKING

from rest_framework import serializers

from scheme.models import SchemeContent, SchemeFee
from ubiquity.versioning.base import serializers as base_serializers

if TYPE_CHECKING:
    from scheme.models import Scheme, SchemeAccount

ServiceConsentSerializer = base_serializers.ServiceConsentSerializer
PaymentCardSerializer = base_serializers.PaymentCardSerializer
TransactionsSerializer = base_serializers.TransactionsSerializer


class MembershipPlanContentSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchemeContent
        exclude = ('id', 'scheme')


class MembershipPlanFeeSerializer(serializers.ModelSerializer):
    type = serializers.CharField(source='fee_type')

    class Meta:
        model = SchemeFee
        exclude = ('id', 'scheme', 'fee_type')


class MembershipPlanSerializer(base_serializers.MembershipPlanSerializer):

    def to_representation(self, instance: 'Scheme') -> dict:
        plan = super().to_representation(instance)
        plan['account']['fees'] = MembershipPlanFeeSerializer(instance.schemefee_set.all(), many=True).data
        plan['content'] = MembershipPlanContentSerializer(instance.schemecontent_set.all(), many=True).data
        return plan


class MembershipCardSerializer(base_serializers.MembershipCardSerializer):
    def to_representation(self, instance: 'SchemeAccount') -> dict:
        card = super().to_representation(instance)

        # TODO: modify this to return actual fields once they have been implemented
        # if 'vouchers' in card:
        #     card['vouchers'].update({
        #         "body_text": "placeholder body text",
        #         "terms_and_conditions_url": "https://www.bink.com"
        #     })

        return card
