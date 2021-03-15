from rest_framework import status
from rest_framework.exceptions import APIException


class AuthFieldError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Missing Auth fields"
    default_code = "auth_field_error"
