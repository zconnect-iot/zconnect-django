from django.conf import settings
from django.db import models
import jsonfield

from .base import ModelBase


class DeviceState(ModelBase):

    """Holds the desired (by the server) and the reported (by the device)
    state

    Note that these should never be updated - just create a new state object

    Attributes:
        desired (dict): Desired (by the server) state of the device for this version
        reported (dict): Reported (by the device) state of the device for this version
        device (Device): Associated device
        version (int): state version
    """

    desired = jsonfield.JSONField(blank=True)
    reported = jsonfield.JSONField(blank=True) # might be blank
    version = models.IntegerField()

    device = models.ForeignKey(settings.ZCONNECT_DEVICE_MODEL, models.CASCADE)

    class Meta:
        ordering = ["created_at"]
        get_latest_by = "created_at"
        unique_together = ["version", "device"]

    @property
    def delta(self):
        """Returns keys in the shadow document which are different between the
        desired and the reported states.

        Example:

            >>> device_state = DeviceState(
            ...     desired={
            ...         "key_1": "abc",
            ...         "key_2": 123,
            ...         "key_3": "blork",
            ...     },
            ...     reported={
            ...         "key_1": "abc",
            ...         "key_2": 456,
            ...         "key_4": "hello",
            ...     },
            ...     version=1,
            ... )

            >>> difference = device_state.delta
            >>> import pprint
            >>> pprint.pprint(difference, indent=2)
            { 'desired': {'key_2': 123, 'key_3': 'blork'},
              'reported': {'key_2': 456, 'key_4': 'hello'}}
        """
        uncommon = {
            "desired": {},
            "reported": {},
        }

        def get_diff(a_name, a, b):
            for key in a:
                if b.get(key) != a[key]:
                    uncommon[a_name][key] = a[key]

        get_diff("reported", self.reported, self.desired)
        get_diff("desired", self.desired, self.reported)

        return uncommon
