"""
Error code notes:

https://en.wikipedia.org/wiki/List_of_HTTP_status_codes
http://www.iana.org/assignments/http-status-codes/http-status-codes.xhtml

4xx client errors, custom error codes are in the range 432-440
5xx service errors, custom error codes are in the range 530-540
"""
from rest_framework.response import Response

INCORRECT_CREDENTIALS = "INCORRECT_CREDENTIALS"
SUSPENDED_ACCOUNT = "SUSPENDED_ACCOUNT"
FACEBOOK_BAD_TOKEN = "FACEBOOK_BAD_TOKEN"
FACEBOOK_CANT_VALIDATE = "FACEBOOK_CANT_VALIDATE"
FACEBOOK_INVALID_USER = "FACEBOOK_INVALID_USER"
FACEBOOK_GRAPH_ACCESS = "FACEBOOK_GRAPH_ACCESS"
INVALID_PROMO_CODE = "INVALID_PROMO_CODE"

errors = {
    INCORRECT_CREDENTIALS: {"code": 403,
                            "message": "Login credentials incorrect."},
    SUSPENDED_ACCOUNT: {"code": 403,
                        "message": "The account associated with this email address is suspended."},
    FACEBOOK_BAD_TOKEN: {"code": 403,
                         "message": "Cannot get facebook user token"},
    FACEBOOK_CANT_VALIDATE: {"code": 403,
                             "message": "Cannot validate user_id & access_token."},
    FACEBOOK_INVALID_USER: {"code": 403,
                            "message": "user_id is invalid for given access token"},
    FACEBOOK_GRAPH_ACCESS: {"code": 403,
                            "message": "Can not access facebook social graph."},
    INVALID_PROMO_CODE: {"code": 403,
                         "message": "The promotion code provided is invalid."}
}


def error_response(error_name):
    error = errors[error_name]
    error['name'] = error_name
    return Response(error, status=error["code"])
