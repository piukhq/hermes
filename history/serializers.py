from rest_framework import serializers

from history.models import (
    HistoricalPaymentCardAccount,
    HistoricalPaymentCardAccountEntry,
    HistoricalSchemeAccount,
    HistoricalSchemeAccountEntry,
)
from payment_card.models import PaymentCardAccount
from scheme.models import SchemeAccount


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


class SchemeAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchemeAccount
        fields = "__all__"


class HistoricalSchemeAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = HistoricalSchemeAccount
        fields = "__all__"


class HistoricalSchemeAccountEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = HistoricalSchemeAccountEntry
        fields = "__all__"


get_history_serializer = {
    "PaymentCardAccount": HistoricalPaymentCardAccountSerializer,
    "PaymentCardAccountEntry": HistoricalPaymentCardAccountEntrySerializer,
    "SchemeAccount": HistoricalSchemeAccountSerializer,
    "SchemeAccountEntry": HistoricalSchemeAccountEntrySerializer,
}

get_body_serializer = {
    "PaymentCardAccount": PaymentCardAccountSerializer,
    "SchemeAccount": SchemeAccountSerializer,
}
