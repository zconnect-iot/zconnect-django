from db_file_storage.model_utils import delete_file, delete_file_if_needed
from django.db import models
from organizations.models import Organization as BaseOrganization

from .base import ModelBase


class Organization(BaseOrganization):

    class Meta:
        proxy = True

    @property
    def parent(self):
        """ Should be overridden by inherited classes to allow
        traversing up a tree of organizations
        """
        return None


class OrganizationLogo(ModelBase):
    organization = models.OneToOneField("Organization", models.CASCADE,
                                        related_name='logo')
    image = models.ImageField(upload_to="zconnect.LogoImage/bytes/filename/mimetype")

    def save(self, *args, **kwargs):
        delete_file_if_needed(self, 'image')
        super(OrganizationLogo, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        super(OrganizationLogo, self).delete(*args, **kwargs)
        delete_file(self, 'image')


class LogoImage(models.Model):
    bytes = models.TextField()
    filename = models.CharField(max_length=255)
    mimetype = models.CharField(max_length=50)
