from rest_framework import serializers
from payment_card.models import PaymentCard, PaymentCardAccount


class PaymentCardSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentCard


class PaymentCardAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentCardAccount
