from django.utils.translation import ugettext_lazy as _
from rest_framework import exceptions, status


class BadRequestError(exceptions.APIException):
    """This is the same as the rest_framework.ValidationError, but for some
    reason that returns a list rather than a dict, which we want to use
    normally"""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = _('Invalid input.')
    default_code = 'invalid'
