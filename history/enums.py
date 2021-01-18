from enum import Enum


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
    def as_tuple(cls):
        return [
            (entry.value, entry.value)
            for entry in cls
        ]
