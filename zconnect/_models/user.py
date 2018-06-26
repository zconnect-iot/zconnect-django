import logging

from django.contrib.auth.models import AbstractUser
from organizations.models import OrganizationUser
from phonenumber_field.modelfields import PhoneNumberField

from zconnect._models import ModelBase

logger = logging.getLogger(__name__)


class User(ModelBase, AbstractUser):

    phone_number = PhoneNumberField(blank=True)

    class Meta(AbstractUser.Meta):
        permissions = (
            ("can_create_timeseries_http", "Can create timeseries data over HTTP"),
        )

    @property
    def orgs(self):
        """Get queryset which behaves like orgs() used to

        This is READ ONLY, you can't just do user.orgs.add() using this
        property. OrganizationUser from django-organizations is badly named, it
        should really be called OrganizationMembership because it is a reference
        between an Organization and a User, not a 'User' by itself.
        """
        return self.organizations_organization

    def add_org(self, org):
        """Add user to an organization

        Args:
            org (Organization): org to add user to

        Returns:
            OrganizationUser: organization membership reference

        Raises:
            django.db.IntegrityError: if the user is already in that org
        """

        membership = OrganizationUser(
            user=self,
            organization=org,
        )
        membership.save()

        return membership
