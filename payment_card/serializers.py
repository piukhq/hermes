from rest_framework import serializers
from payment_card.models import PaymentCard, PaymentCardAccount
from scheme.models import SchemeAccount


class PaymentCardSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentCard


class PaymentCardAccountSerializer(serializers.ModelSerializer):
    status_name = serializers.ReadOnlyField()

    class Meta:
        model = PaymentCardAccount
        extra_kwargs = {'token': {'write_only': True}}
        read_only_fields = ('status', )


class PaymentCardSchemeAccountSerializer(serializers.Serializer):
    scheme_id = serializers.ReadOnlyField()
    user_id = serializers.ReadOnlyField()
    scheme_account_id = serializers.ReadOnlyField()
