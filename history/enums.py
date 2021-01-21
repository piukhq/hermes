from enum import Enum
from typing import TYPE_CHECKING, Type

from rest_framework.utils.model_meta import get_field_info

if TYPE_CHECKING:
    from django.db.models import Model


class HistoryModel(Enum):
    PAYMENT_CARD_ACCOUNT = "payment_card.PaymentCardAccount"
    PAYMENT_CARD_ACCOUNT_ENTRY = "ubiquity.PaymentCardAccountEntry"
    SCHEME_ACCOUNT = "scheme.SchemeAccount"
    SCHEME_ACCOUNT_ENTRY = "ubiquity.SchemeAccountEntry"

    @property
    def model_name(self):
        return self.value.split(".")[-1]

    @property
    def historic_model_name(self):
        return f"Historical{self.model_name}"

    def __str__(self):
        return self.model_name

    def __eq__(self, value):
        return self.model_name == value


class SchemeAccountJourney(Enum):
    NONE = "n/a"
    ADD = "add"
    REGISTER = "register"
    ENROL = "enrol"

    @classmethod
    def as_tuple_tuple(cls):
        return [(entry.value, entry.value) for entry in cls]


class ExcludedFields(Enum):
    """
    These fields are used as cache layer for performance purposes, but they are not logically part of the cards.
    """

    PLL_LINKS = "pll_links"
    FORMATTED_IMAGES = "formatted_images"
    BALANCES = "balances"
    VOUCHERS = "vouchers"
    TRANSACTIONS = "transactions"

    @classmethod
    def as_set(cls):
        return {entry.value for entry in cls}

    @classmethod
    def as_tuple(cls, filter_for: Type["Model"] = None):
        if filter_for:
            allowed_fields = get_field_info(filter_for).fields.keys()
        else:
            allowed_fields = []

        return tuple(entry.value for entry in cls if entry.value in allowed_fields)
