# https://github.com/dfunckt/django-rules#best-practices

import logging

from django.conf import settings
from django.db import models
import rules

logger = logging.getLogger(__name__)


@rules.predicate
def can_view_device(user, obj):
    """Check that a user is in the same organization as the Device

    Args:
        user (User): User to check permissions for
        obj (Device): Device to check organizations

    Returns:
        bool: If the user has any organizations in common with the Device, or is
            a superuser
    """
    if user.is_superuser:
        logger.debug("Superuser can access any device")
        return True

    from organizations.models import Organization

    all_orgs = Organization.objects.filter(
        models.Q(pk__in=user.orgs.all()) & models.Q(pk__in=obj.orgs.all())
    )

    return any(all_orgs)


device_model = settings.ZCONNECT_DEVICE_MODEL
module, _, model = device_model.partition(".")

if not (model and module):
    raise RuntimeError("Expected ZCONNECT_DEVICE_MODEL to be in the form 'module.modelname'")

rules.add_perm(
    "{}.view_{}".format(module, model).lower(),
    can_view_device,
)
rules.add_perm(
    "{}.change_{}".format(module, model).lower(),
    can_view_device,
)
rules.add_perm(
    "{}.delete_{}".format(module, model).lower(),
    rules.always_deny,
)
