from rest_framework import status
from rest_framework.exceptions import APIException


class ServiceUnavailable(APIException):
    status_code = 500
    default_detail = 'Credentials Incomplete'


class UserConflictError(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Attempting to create two or more identical users at the same time."
    default_code = "conflict"


class MagicLinkExpiredTokenError(APIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = "Token is expired."
    default_code = "unauthorised"


class MagicLinkValidationError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Token is invalid."
    default_code = "invalid"
