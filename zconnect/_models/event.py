import logging

# from django.contrib.postgres.fields import JSONField
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
import jsonfield

from .base import ModelBase

logger = logging.getLogger(__name__)


class EventDefinition(ModelBase):
    """Defines an event that should be triggered when a certain condition is met
    on a device

    Actions are just dynamic fields so can be just about anything as long as
    there is a matching action handler in a plugin

    Example:
        For example, send an email to a user if a door is left unlocked after 5pm
        might look something like:

            {
                "condition": "door_open && time > 17:00",
                "actions": {
                    "send_email":{
                        "subj": "DOOR STUCK",
                        "body": "please close door"
                    }
                }
            }

    Note:
        These can be set for Products and Devices, think about this when
        setting 'enabled' etc.

    Attributes:
        actions (dict): Dictionary describing what actions to take when the
            event is triggered
        condition (str): When to match this condition. In the form of something
            like "x>y && z|a == 7". Look at docs for condition parser for more
            information
        debounce_window (int, 600): How often to send this event, in seconds. If
            set too low then it will trigger the events very often.
        enabled (bool, True): Whether this event is enabled.
        ref (str): Description of event (eg, "door stuck")
        scheduled (bool, False): Whether this event is scheduled to happen every
            so often. This is used by celery tasks that run every minute to see
            whether the event should be triggerd. if the condition is not time
            based, this is automatically reset to False.
        single_trigger (bool, False): ???
    """

    enabled = models.BooleanField(default=True)
    ref = models.CharField(max_length=100)
    condition = models.CharField(max_length=100, blank=False)
    actions = jsonfield.JSONField(blank=False)
    debounce_window = models.IntegerField(default=600)  # seconds
    scheduled = models.BooleanField(default=False)
    single_trigger = models.BooleanField(default=False)
    deleted = models.BooleanField(default=False)

    device = models.ForeignKey(settings.ZCONNECT_DEVICE_MODEL, null=True, blank=True,
                               on_delete=models.CASCADE, related_name="event_defs")
    product = models.ForeignKey("Product", null=True, blank=True,
                               on_delete=models.CASCADE, related_name="event_defs")

    def clean(self):
        if not self.device and not self.product:
            raise ValidationError('Event Definitions must have either a device or a product')
        if self.device and self.product:
            raise ValidationError('Event Definition cannot have both a device and a product')

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        if self.product:
            return '{self.condition} (product: {self.product})'.format(self=self)
        else:
            return '{self.condition} (device: {self.device})'.format(self=self)


class Event(ModelBase):
    """An event is an instance of an event triggered by an
    event definition

    Attributes:
        device (Device): Device associated with this event
        event (EventDefinition): What defintion triggered this event
        success (bool, False): Whether this event was successfully triggered
    """
    device = models.ForeignKey(settings.ZCONNECT_DEVICE_MODEL, models.CASCADE, blank=False)
    success = models.BooleanField(default=False)
    definition = models.ForeignKey("EventDefinition", models.CASCADE, related_name="event")
