import logging
import time

from django.apps import apps
from django.conf import settings
from ibmiotf.application import Client

from ..message import Message

logger = logging.getLogger(__name__)

class IBMInterface(Client):
    ibm_settings = {}

    def __init__(self, broker_settings):
        """ Provides a standardised interface to the Watson IoT client which
            can then be swapped out with other broker implementations.
        """

        zlogger = logging.getLogger("zconnect")
        log_handlers = broker_settings.get("logHandlers", zlogger.handlers)

        logger.debug("Connecting to ibm with %s", broker_settings)

        super().__init__(broker_settings, logHandlers=log_handlers)

        self.client.on_message = self.onUnsupportedMessage

        for i in range(10):
            try:
                self.connect()
            except:  # pylint: disable=broad-except,bare-except
                if i >= 9:
                    raise
                time.sleep(i)
            else:
                break

    def send_message(self, category, body, device_id, device_type):
        """ Send a message to a device.

        See documentation for sender for arguments.

        This expects that the device has already been resolved
        """

        logger.info("sending command as %s, with type %s, message %s",
                    device_id, device_type, str(body))
        res = self.publishCommand(device_type, device_id, category, "json", data=body,
                                  qos=1)

        if not res:
            logger.warning("Unable to send command")

    def send_as_device(self, category, body, device_id, device_type):
        """ Send an event as if it were from a device.

        See documentation for sender for arguments.

        This expects that the device has already been resolved
        """
        logger.info("sending event as device with id %s, type %s and body %s",
                    device_id, device_type, str(body))
        res = self.publishEvent(device_type, device_id, category, "json-iotf", data=body,
                                qos=1)

        if not res:
            logger.warning("Unable to send command")

    def generate_event_callback(self, callback):
        """ Given a function which takes a zconnect message, return an
            equivalent function which takes a Watson IoT event instead

        Args:
            callback (function) A function with a single argument, message
        """
        def processed_callback(event):
            message = self.construct_zconnect_message(event)
            callback(message)

        return processed_callback

    def generate_status_callback(self, callback):
        """ Given a function which takes a zconnect message, return an
            equivalent function which takes a Watson IoT event with category
            'status' and the event's action as its body instead

        Args:
            callback (function) A function with a single argument, message
        """
        def processed_callback(event):
            Device = apps.get_model(settings.ZCONNECT_DEVICE_MODEL)
            device = Device.objects.get(pk=event.deviceId)
            message = Message(category="status", body=event.action,
                              device=device)
            callback(message)

        return processed_callback

    def subscribe_to_events(self, callback):
        """ Given a callback (passed in by listener.py), create two versions of
            that function which take Waston IoT events and statuses. When
            when status messages and events come in, pass them to these
            functions

        Args:
            callback (function) A function with a single argument, message
        """
        # false positive
        # pylint: disable=attribute-defined-outside-init
        self.deviceEventCallback = self.generate_event_callback(callback)
        self.deviceStatusCallback = self.generate_status_callback(callback)
        self.subscribeToDeviceEvents()
        self.subscribeToDeviceStatus()

        self.client.subscribe("/ping", qos=0)

    def onUnsupportedMessage(self, client, userdata, message):
        """Override built in ibm version of this

        it does the same thing - just log a warning
        """
        if message.topic == "/ping":
            self.client.publish("/pong", "pong", qos=1)
        else:
            self.logger.warning("Received '%s' on unsupported topic '%s'", message.payload, message.topic)

    def construct_zconnect_message(self, event):
        """ Converts a Watson IoT Event into a Zconnect Message object

        Args:
            event (Watson IoT event or status) Event to convert
        """

        try:
            category = event.event
        except AttributeError:
            category = "status"

        try:
            body = event.data
        except AttributeError:
            body = event.payload

        try:
            timestamp = event.timestamp
        except AttributeError:
            timestamp = None

        Device = apps.get_model(settings.ZCONNECT_DEVICE_MODEL)
        device = Device.objects.get(pk=event.deviceId)

        return Message(category=category, body=body, device=device, timestamp=timestamp)
