import sys
from typing import Type

from rest_framework import serializers

from history.enums import ExcludedFields
from history.models import (
    HistoricalPaymentCardAccount,
    HistoricalPaymentCardAccountEntry,
    HistoricalSchemeAccount,
    HistoricalSchemeAccountEntry,
)
from payment_card.models import PaymentCardAccount
from scheme.models import SchemeAccount


class HistoricalPaymentCardAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = HistoricalPaymentCardAccount
        fields = "__all__"


class HistoricalPaymentCardAccountEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = HistoricalPaymentCardAccountEntry
        fields = "__all__"


class HistoricalSchemeAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = HistoricalSchemeAccount
        fields = "__all__"


class HistoricalSchemeAccountEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = HistoricalSchemeAccountEntry
        fields = "__all__"


class ReadOnlyModelSerializer(serializers.ModelSerializer):
    def get_fields(self, *args, **kwargs):
        fields = super().get_fields(*args, **kwargs)
        for field in fields:
            fields[field].read_only = True
        return fields


class PaymentCardAccountSerializer(ReadOnlyModelSerializer):
    class Meta:
        model = PaymentCardAccount
        exclude = ExcludedFields.as_tuple(PaymentCardAccount)


class SchemeAccountSerializer(ReadOnlyModelSerializer):
    class Meta:
        model = SchemeAccount
        exclude = ExcludedFields.as_tuple(SchemeAccount)


def _get_serializer(name: str) -> Type["serializers.Serializer"]:
    return getattr(sys.modules[__name__], name)


def get_historical_serializer(name: str) -> Type["serializers.Serializer"]:
    return _get_serializer(f"Historical{name}Serializer")


def get_body_serializer(name: str) -> Type["serializers.Serializer"]:
    return _get_serializer(f"{name}Serializer")
