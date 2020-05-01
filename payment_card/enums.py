from enum import Enum, auto


class PaymentCardRoutes(Enum):
    NEW_CARD = auto()
    DELETED_CARD = auto()
    ALREADY_IN_WALLET = auto()
    EXISTS_IN_OTHER_WALLET = auto()


class RequestMethod(str, Enum):
    GET = 'GET'
    POST = 'POST'
    PATCH = 'PATCH'
    PUT = 'PUT'
    DELETE = 'DELETE'
