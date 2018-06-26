import logging

from rest_framework import permissions

# import rules


logger = logging.getLogger(__name__)


class GroupPermissions(permissions.DjangoObjectPermissions):
    """Extend default permissions (see source of DjangoObjectPermissions for
    original)

    This also checks on a *PER OBJECT* basis whether the user has permissions to
    make the particular request for each object - ie, if we go a PUT on a
    device, it makes sure the user has the change_device permission on that
    particular object.

    Handled via django-guardian/permissions_classes on the viewset
    """
    perms_map = {
        # Let people query these endpoints - the results should be filtered as
        # mentioned above
        'GET': [],
        'OPTIONS': [],
        'HEAD': [],
        # 'GET': ['%(app_label)s.view_%(model_name)s'],
        # 'OPTIONS': ['%(app_label)s.view_%(model_name)s'],
        # 'HEAD': ['%(app_label)s.view_%(model_name)s'],

        'POST': ['%(app_label)s.add_%(model_name)s'],
        'PUT': ['%(app_label)s.change_%(model_name)s'],
        'PATCH': ['%(app_label)s.change_%(model_name)s'],

        # Maybe don't let a user delete devices
        'DELETE': ['%(app_label)s.delete_%(model_name)s'],
    }


class NestedGroupPermissions(GroupPermissions):
    """Similar to above but for use in nested viewsets

    Makes it so that if somebody does a delete to
    `/api/v3/devices/1/eventdefs/2`, if just makes sure that the user has the
    change_device permission, rather than requiring delete_device, which most
    users will not have.

    This assumes that all 'nested' objects are only ever related to that object,
    or else a user could delete data that is used by another device.

    SHOULD NOT be used directly - will be dynamically added as required
    """
    perms_map = {
        # These should be inherited
        'GET': GroupPermissions.perms_map["GET"],
        'OPTIONS': GroupPermissions.perms_map["OPTIONS"],
        'HEAD': GroupPermissions.perms_map["HEAD"],

        'POST': ['%(app_label)s.change_%(model_name)s'],
        'PUT': ['%(app_label)s.change_%(model_name)s'],
        'PATCH': ['%(app_label)s.change_%(model_name)s'],
        'DELETE': ['%(app_label)s.change_%(model_name)s'],
    }


class IsAdminOrReadOnly(permissions.BasePermission):
    message = "Only admins are allowed to modify."

    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            (
                request.user.is_staff or
                request.user.is_superuser or
                request.method in ('GET', 'HEAD', 'OPTIONS')
            )
        )

class IsAuthenticatedAdminPost(permissions.BasePermission):
    message = "Only admins are allowed to create users, Authenticated can perform all other \
    requests."

    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            (
                request.method != 'POST' or
                request.user.is_staff or
                request.user.is_superuser
            )
        )


class IsAdminOrTimeseriesIngress(permissions.BasePermission):
    message = "Only admins or users with timeseries write permissions can create timeseries data."

    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.method == 'POST' and
            (
                request.user.is_superuser or
                request.user.has_perm('zconnect.can_create_timeseries_http')
            )
        )
