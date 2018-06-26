import logging

import django
from django.conf import settings
from django.db import models
from rest_auth.utils import import_callable

from zconnect._models.base import ModelBase

logger = logging.getLogger(__name__)


class DeviceUpdateStatus(ModelBase):
    """Information about running a particular update on a certain device

    Attributes:
        attempted (bool): Whether it has actually been triggered/attempted on
            this device - can only be true if the device was online at some
            point (eg 'time' must be non-null)
        device (Device): Which device the update was attempted on
        error_message (str): What the error was - should be returned from the
            device in an MQTT message
        execution (UpdateExecution): Which update execution this triggered
        success (bool): Whether it successfully updated this device
        time (datetime): When the update was attempted
    """
    time = models.DateTimeField(blank=True, null=True)
    device = models.ForeignKey(settings.ZCONNECT_DEVICE_MODEL, models.CASCADE, blank=False)
    # This could be pretty big?
    error_message = models.CharField(max_length=500)
    execution = models.ForeignKey("UpdateExecution", models.CASCADE, related_name="failed_updates", blank=False)
    attempted = models.BooleanField(default=False)
    success = models.BooleanField(default=False)


class UpdateExecution(ModelBase):
    """
    Stores information about an update strategies application
    to a set of devices

    This will store state about the update's progress.

    Attributes:
        enabled (bool, True): Whether this update should be triggered or not
        product_firmware (ProductFirmware): The firmware that is sent in the
            update
        strategy_class (str): Which strategy to use for this update. Should be a
            direct reference to the class, in a form like
            "zconnect.updates.SimpleStrategy"
        update_state (dict): Dynamic field which holds generic state of the
            update, which is different depending on the update strategy
    """
    product_firmware = models.ForeignKey("ProductFirmware", models.CASCADE, blank=False)
    strategy_class = models.CharField(max_length=30)

    enabled = models.BooleanField(default=False)

    # update_state = DynamicField()

    @classmethod
    def pre_save(cls, sender, document, **kwargs):
        # pylint: disable=unused-argument
        try:
            strategy_hook = import_callable(document.strategy_class)
        except ImportError as e:
            raise django.core.exceptions.ValidationError("Invalid strategy class '{}'".format(document.strategy_class)) from e

        strategy_hook.on_create(document)

    def __str__(self):
        return "UpdateExecution: firmware: {}, strategy: {}, " \
               "devices_completed: {}, devices_to_update: {}".format(
            self.product_firmware.id, self.strategy_class,
            self.devices_completed, self.devices_to_update
        )
