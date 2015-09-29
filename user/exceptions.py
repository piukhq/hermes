from rest_framework.exceptions import APIException


class ServiceUnavailable(APIException):
    status_code = 500
    default_detail = 'Credentials Incomplete'
