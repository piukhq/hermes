import sys
from collections import OrderedDict
from typing import Type

from rest_framework import serializers

from history.enums import ExcludedField
from history.models import (
    HistoricalPaymentCardAccount,
    HistoricalPaymentCardAccountEntry,
    HistoricalSchemeAccount,
    HistoricalSchemeAccountEntry,
    HistoricalCustomUser,
)
from payment_card.models import PaymentCardAccount
from scheme.models import SchemeAccount
from user.models import CustomUser


# ----- serializers used to validate and save historical models ----- #


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


class HistoricalCustomUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = HistoricalCustomUser
        fields = "__all__"


# ----- serializers used to serialize cards' body field. ----- #


class ReadOnlyModelSerializer(serializers.ModelSerializer):
    def get_fields(self):
        fields = super().get_fields()
        filtered_fields = OrderedDict()
        for k, v in fields.items():
            if not isinstance(v, serializers.ManyRelatedField):
                filtered_fields[k] = v
                filtered_fields[k].read_only = True

        del fields
        return filtered_fields


class CustomUserSerializer(ReadOnlyModelSerializer):
    class Meta:
        model = CustomUser
        exclude = ExcludedField.as_tuple(CustomUser)


class PaymentCardAccountSerializer(ReadOnlyModelSerializer):
    class Meta:
        model = PaymentCardAccount
        exclude = ExcludedField.as_tuple(PaymentCardAccount)


class SchemeAccountSerializer(ReadOnlyModelSerializer):
    class Meta:
        model = SchemeAccount
        exclude = ExcludedField.as_tuple(SchemeAccount)


def _get_serializer(name: str) -> Type["serializers.Serializer"]:
    return getattr(sys.modules[__name__], name)


def get_historical_serializer(name: str) -> Type["serializers.Serializer"]:
    return _get_serializer(f"Historical{name}Serializer")


def get_body_serializer(name: str) -> Type["serializers.Serializer"]:
    return _get_serializer(f"{name}Serializer")
