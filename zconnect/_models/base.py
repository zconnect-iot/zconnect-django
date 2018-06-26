from django.db import models


class ModelBase(models.Model):
    """
    An abstract base class model
    """
    class Meta:
        abstract = True

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
