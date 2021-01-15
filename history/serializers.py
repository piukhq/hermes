from rest_framework import serializers

from history.models import HistoricalPaymentCardAccount, HistoricalPaymentCardAccountEntry
from payment_card.models import PaymentCardAccount


class PaymentCardAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentCardAccount
        fields = "__all__"


class HistoricalPaymentCardAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = HistoricalPaymentCardAccount
        fields = "__all__"


class HistoricalPaymentCardAccountEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = HistoricalPaymentCardAccountEntry
        fields = "__all__"


get_history_serializer = {
    "PaymentCardAccount": HistoricalPaymentCardAccountSerializer,
    "PaymentCardAccountEntry": HistoricalPaymentCardAccountEntrySerializer
}

get_body_serializer = {
    "PaymentCardAccount": PaymentCardAccountSerializer
}
