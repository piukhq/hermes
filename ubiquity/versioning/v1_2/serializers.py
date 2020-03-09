from typing import TYPE_CHECKING

from ubiquity.versioning.base import serializers as base_serializers

if TYPE_CHECKING:
    from scheme.models import Scheme, SchemeAccount

PaymentCardSerializer = base_serializers.PaymentCardSerializer
TransactionsSerializer = base_serializers.TransactionsSerializer


class MembershipPlanSerializer(base_serializers.MembershipPlanSerializer):

    def to_representation(self, instance: 'Scheme') -> dict:
        plan = super().to_representation(instance)

        # TODO: modify this to return actual fees once they have been implemented
        plan['fees'] = [{"amount": 1.1, "type": "enrolment"}]

        # TODO: modify this to return actual dynamic content once it has been implemented
        plan['content'] = [{"column": "content column", "value": "content value"}]

        return plan


class MembershipCardSerializer(base_serializers.MembershipCardSerializer):
    def to_representation(self, instance: 'SchemeAccount') -> dict:
        card = super().to_representation(instance)

        # TODO: modify this to return actual fields once they have been implemented
        if 'vouchers' in card:
            card['vouchers'].update({
                "body_text": "example body text",
                "terms_and_conditions_url": "https://www.bink.com"
            })

        return card
