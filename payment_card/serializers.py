from rest_framework import serializers
from payment_card.models import PaymentCard, PaymentCardAccount


class PaymentCardSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentCard


class PaymentCardAccountSerializer(serializers.ModelSerializer):
    status_name = serializers.ReadOnlyField()

    class Meta:
        model = PaymentCardAccount
        extra_kwargs = {'token': {'write_only': True}}
        read_only_fields = ('status', )
