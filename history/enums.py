from enum import Enum
from typing import TYPE_CHECKING, Type, Optional, Tuple, Union, List, Iterable

if TYPE_CHECKING:
    from django.db.models import Model


class HistoryModel(Enum):
    PAYMENT_CARD_ACCOUNT = "payment_card.PaymentCardAccount"
    PAYMENT_CARD_ACCOUNT_ENTRY = "ubiquity.PaymentCardAccountEntry"
    SCHEME_ACCOUNT = "scheme.SchemeAccount"
    SCHEME_ACCOUNT_ENTRY = "ubiquity.SchemeAccountEntry"
    CUSTOM_USER = "user.CustomUser"
    VOP_ACTIVATION = "ubiquity.VopActivation"
    PAYMENT_CARD_SCHEME_ENTRY = "ubiquity.PaymentCardSchemeEntry"

    @property
    def model_name(self):
        return self.value.split(".")[-1]

    @property
    def historic_model_name(self):
        return f"Historical{self.model_name}"

    @property
    def historic_serializer_name(self):
        return f"{self.historic_model_name}Serializer"


class SchemeAccountJourney(Enum):
    NONE = "n/a"
    ADD = "add"
    REGISTER = "register"
    ENROL = "enrol"

    @classmethod
    def as_tuple_list(cls) -> List[tuple]:
        return [(entry.value, entry.value) for entry in cls]


class ExcludedField(Enum):
    """
    These fields are used as cache layer for performance purposes, but they are not logically part of the cards.
    """

    PLL_LINKS = "pll_links"
    FORMATTED_IMAGES = "formatted_images"
    BALANCES = "balances"
    VOUCHERS = "vouchers"
    TRANSACTIONS = "transactions"

    @classmethod
    def as_set(cls) -> set:
        return {entry.value for entry in cls}

    @classmethod
    def as_list(cls, filter_for: Type["Model"] = None) -> List[str]:
        if filter_for:
            allowed_fields = [field.attname for field in filter_for._meta.fields]
        else:
            allowed_fields = []

        return [entry.value for entry in cls if entry.value in allowed_fields]


class DeleteField(Enum):
    IS_DELETED = "is_deleted"
    IS_ACTIVE = "is_active"
    NONE = "n/a"

    def get_value(self, objs: Union[Iterable, Type["Model"]] = None) -> Tuple[Optional[str], bool]:
        if not objs:
            field_value = False

        elif isinstance(objs, Iterable):
            field_value = all(getattr(obj, self.value) for obj in objs)
        else:
            field_value = getattr(objs, self.value)

        if self == self.IS_ACTIVE:
            field_value = not field_value

        return self.value, field_value
