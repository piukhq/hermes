from enum import Enum, StrEnum, auto


class PaymentCardRoutes(Enum):
    NEW_CARD = auto()
    DELETED_CARD = auto()
    ALREADY_IN_WALLET = auto()
    EXISTS_IN_OTHER_WALLET = auto()


class RequestMethod(StrEnum):
    GET = "GET"
    POST = "POST"
    PATCH = "PATCH"
    PUT = "PUT"
    DELETE = "DELETE"


class RetryTypes(StrEnum):
    REMOVE = "remove"
    REDACT = "redact"
    REMOVE_AND_REDACT = "remove_and_redact"

    def get_task_name(self):
        match self:
            case RetryTypes.REMOVE:
                return "retry_delete_payment_card"
            case RetryTypes.REDACT:
                return "retry_redact_payment_card"
            case RetryTypes.REMOVE_AND_REDACT:
                return "retry_delete_and_redact_payment_card"
            case _:
                raise ValueError(f"unexpected RetryTypes' value {self.name}")
