import logging

from django.db import models
from organizations.models import Organization

from .base import ModelBase
from .user import User

logger = logging.getLogger(__name__)


class ActivitySubscription(ModelBase):
    """ Represents user subscriptions to activities

    Attributes:
        user (fk): The user making the subscription
        organization (OneToOne): Organization the user must be a part of to
            recieve notifications for this subscription
        category (char): The event category, e.g. `business metrics`
        min_severity (int): A minimum severity which will trigger the
            notifiction

        type (char): The type for this subscription. Multiple subscriptions
            can be made for different mediums
    """
    class Meta:
        # Ensure user cannot create duplicate subscriptions
        unique_together = ["user", "organization", "category", "min_severity", "type"]

    SEVERITY_CHOICES = [(0, 0), (10, 10), (20, 20), (30, 30), (40, 40), (50, 50)]
    TYPE_CHOICES = [('sms', 'sms'), ('email', 'email'), ('push', 'push')]

    user = models.ForeignKey(
        User,
        models.PROTECT,
    )
    organization = models.ForeignKey(
        Organization,
        models.PROTECT,
    )
    category = models.CharField(max_length=50)
    min_severity = models.IntegerField(choices=SEVERITY_CHOICES, default=0)
    type = models.CharField(choices=TYPE_CHOICES, max_length=50)
