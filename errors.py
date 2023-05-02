"""
Error code notes:

https://en.wikipedia.org/wiki/List_of_HTTP_status_codes
http://www.iana.org/assignments/http-status-codes/http-status-codes.xhtml

4xx client errors, custom error codes are in the range 432-440
5xx service errors, custom error codes are in the range 530-540
"""
from rest_framework.response import Response

INCORRECT_CREDENTIALS = "INCORRECT_CREDENTIALS"
INVALID_PROMO_CODE = "INVALID_PROMO_CODE"
REGISTRATION_FAILED = "REGISTRATION_FAILED"

errors = {
    INCORRECT_CREDENTIALS: {"code": 403, "message": "Login credentials incorrect."},
    INVALID_PROMO_CODE: {"code": 403, "message": "The promotion code provided is invalid."},
    REGISTRATION_FAILED: {"code": 403, "message": "Registration failed."},
}


def error_response(error_name):
    error = errors[error_name]
    error["name"] = error_name
    return Response(error, status=error["code"])
