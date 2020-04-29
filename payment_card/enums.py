from enum import Enum

from rest_framework import status


class PaymentCardRoutes(Enum):
    NEW_CARD = status.HTTP_201_CREATED
    DELETED_CARD = status.HTTP_201_CREATED
    ALREADY_IN_WALLET = status.HTTP_200_OK
    EXISTS_IN_OTHER_WALLET = status.HTTP_201_CREATED
