import logging

from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.views import exception_handler


logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    logger.debug(exc, exc_info=True)

    return response


class AuthFieldError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Missing Auth fields"
    default_code = "auth_field_error"
