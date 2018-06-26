import functools
import logging

from django.contrib.auth import get_user_model
from django_filters.rest_framework import CharFilter, FilterSet
from rest_framework import filters

from .models import EventDefinition

logger = logging.getLogger(__name__)


def wildcard_filter(queryset, name, value):
    if not value:
        return queryset
    elif value[0] == '*' and value[-1] == '*':
        kwargs = {'{}__contains'.format(name): value.replace('*', '')}
    elif value[0] == '*':
        kwargs = {'{}__endswith'.format(name): value.replace('*', '')}
    elif value[-1] == '*':
        kwargs = {'{}__startswith'.format(name): value.replace('*', '')}
    else:
        kwargs = {'{}'.format(name): value.replace('*', '')}
    return queryset.filter(**kwargs)


class EventDefinitionFilterSet(FilterSet):
    ref = CharFilter(name="ref", method=wildcard_filter)

    class Meta:
        model = EventDefinition
        fields = ['ref']


class UserFilterSet(FilterSet):
    email = CharFilter(name="email", method=wildcard_filter)
    last_name = CharFilter(name="last_name", method=wildcard_filter)

    class Meta:
        model = get_user_model()
        fields = ["email", "last_name"]


class OrganizationObjectPermissionsFilter(filters.BaseFilterBackend):
    """Similar to DjangoObjectPermissionsFilter, but because we don't store any
    organization level permissions in the database we just filter on
    organizations first, then load the queryset and check permissions for each
    object.
    """

    perm_format = '%(app_label)s.view_%(model_name)s'

    def filter_queryset(self, request, queryset, view):
        # From DjangoObjectPermissionsFilter
        user = request.user

        if user.is_superuser:
            logger.debug("Superuser can access anything")
            return queryset

        model_cls = queryset.model
        kwargs = {
            'app_label': model_cls._meta.app_label,
            'model_name': model_cls._meta.model_name
        }
        permission = self.perm_format % kwargs

        # 1. Iterate over all results and check has_perm
        # 2. Get ids of all objects in resulting list
        # 3. Return a new queryset with pk__in=[filtered]

        # This is just an intermediary step to filter by devices that are
        # availble to the user, not checking permissions but reducing the amount
        # of results we have to check with has_perm
        # XXX
        # This works for single-level organizations, but not multi-level ones
        # intermediary_qs = queryset.filter(orgs__in=user.orgs.all())
        intermediary_qs = queryset.all()

        if intermediary_qs.count() == 0:
            logger.debug("No %s objects in the same organization", queryset.model)
            return queryset.none()

        if not user.orgs.all():
            logger.debug("User in no organizations")
            return queryset.none()

        logger.debug("Checking '%s' has '%s' on %d of '%s'", user, permission,
            queryset.count(), queryset.model)

        # if logger.isEnabledFor(logging.DEBUG):
        #     logger.debug("available: %s", list(intermediary_qs.all()))
        #     def print_orgs(org):
        #         logger.debug("  %s", org.name)
        #     logger.debug("User orgs:")
        #     for org in user.orgs.all():
        #         print_orgs(org)
        #     logger.debug("object orgs:")
        #     for obj in queryset.all():
        #         logger.debug(" %s:", obj.id)
        #         for org in obj.orgs.all():
        #             print_orgs(org)

        bound = functools.partial(user.has_perm, permission)
        filtered = filter(bound, intermediary_qs.all())
        new_qs = queryset.filter(pk__in=[f.pk for f in filtered])

        return new_qs
