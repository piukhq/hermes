from enum import Enum

from rest_framework import status


class PaymentCardRoutes(Enum):
    IS_DELETED = status.HTTP_201_CREATED
    ALREADY_IN_WALLET = status.HTTP_200_OK
    EXISTS_IN_OTHER_WALLET = status.HTTP_201_CREATED
    NEW_CARD = status.HTTP_201_CREATED
