from rest_framework.exceptions import APIException


class DeviceLookupException(APIException):
    status_code = 400
    default_detail = "Could not lookup device"
    default_code = "bad_request"
