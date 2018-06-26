import abc
from datetime import datetime, timedelta
import logging

from django.apps import apps
from django.conf import settings

logger = logging.getLogger(__name__)


class UpdateStrategy(metaclass=abc.ABCMeta):
    """
    Base class for all update strategies.
    Children should modify the description appropriately
    """
    description = "Generic Update Strategy"

    @abc.abstractclassmethod
    def on_create(cls, fw_execution):
        # pylint: disable=unused-argument
        """
        Creation hook for update executions.
        Will be called when the UpdateExecution model is created but before it
        is saved to mongodb
        Args:
            fw_execution

        Returns:

        """

    @abc.abstractclassmethod
    def apply(cls, fw_execution, watson):
        # pylint: disable=unused-argument
        """
        Apply an update strategy
        Args:
            fw_execution:
            watson:

        Returns:

        """

    @abc.abstractclassmethod
    def on_update_complete(cls, fw_execution, device):
        # pylint: disable=unused-argument
        """
        Hook for after an update has successfully been applied to a device
        This should only be called after the lists in the updateExecution have been
        updated.
        Args:
            fw_execution: The UpdateExecution document that was applied
            device: The device which successfully completed the update

        Returns:

        """


class SimpleUpdate(UpdateStrategy):
    """
    Roll out the update to all available devices at the same time.
    """
    description = "A simple update strategy to roll out updates immediately " \
                  "to all devices"

    # The min time to wait between update attempts
    update_attempt_interval = 3600

    @classmethod
    def on_create(cls, fw_execution):
        logger.debug("Simple update strategy created. Creating list of devices "
                     "to update")

        product_firmware = fw_execution.product_firmware
        product = product_firmware.product

        device_model = apps.get_model(settings.ZCONNECT_DEVICE_MODEL)
        devices_to_update = list(device_model.objects(product=product).all())

        logger.debug("Updating the following devices: %s",
                     [device.id for device in devices_to_update])

        fw_execution.devices_to_update = devices_to_update

    @classmethod
    def apply(cls, fw_execution, watson):
        logger.info("Applying simple update strategy for fw_execution %s",
                     fw_execution.id)

        # If we don't have any state yet, create it in the right format
        if not fw_execution.update_state:
            fw_execution.update_state = {
                "last_sent": {},
            }

        product_firmware = fw_execution.product_firmware

        update_payload = {
            "url": product_firmware.download_url,
            "version": product_firmware.fw_version_string,
            "update_id": fw_execution.id,
        }

        logger.debug("Devices to update: %s", fw_execution.devices_to_update)

        # Loop through the devices in the incomplete list and send the update
        for device_to_update in fw_execution.devices_to_update:
            # If the device is not online, then don't update it.
            if not device_to_update.online:
                logger.debug("Not updating %s because it's not online",
                             device_to_update.id)
                continue

            now = datetime.utcnow()
            last_sent_time = fw_execution.update_state['last_sent'].get(
                str(device_to_update.id), None)

            # If we've sent the update within the last X seconds, don't send again
            if last_sent_time:
                time_diff = now - last_sent_time
                if time_diff < timedelta(seconds=cls.update_attempt_interval):
                    logger.debug("Not updating %s because an update was attempted "
                                 "within the last %s seconds",
                                 device_to_update.id,
                                 cls.update_attempt_interval)
                    continue

            logger.info("Sending firmware update (v: %s) to device: %s",
                        product_firmware.fw_version_string,
                        device_to_update.id)

            watson.send_message_to_device(
                    device_to_update, "update", update_payload
                )

            # Update the last sent time for this device.
            copied_update_state = fw_execution.update_state.copy()
            copied_update_state['last_sent'][str(device_to_update.id)] = now
            fw_execution.update_state = copied_update_state

        fw_execution.save()

    @classmethod
    def on_update_complete(cls, fw_execution, device):
        # pylint: disable=unused-argument
        pass


class StaggeredUpdate(UpdateStrategy):
    description = "Stagger an update over a period of time and stop the update " \
                  "rollout if the failure rate is too high."
