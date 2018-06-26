import logging

from django.apps import apps
from django.conf import settings

from zconnect import zsettings
from zconnect.util.general import load_from_module

logger = logging.getLogger(__name__)


class Sender:

    """Abstract interface for sending messages to devices

    This will pass a generic Message to the sender implementation to send to the
    specified device
    """

    def __init__(self):
        sender_settings = dict(zsettings.SENDER_SETTINGS)
        cls_name = sender_settings.get("cls", "zconnect.messages.IBMInterface")
        interface_class = load_from_module(cls_name)
        self.interface = interface_class(sender_settings)

    def to_device(self, category, body, device=None, device_id=None,
            incoming_message=None, **kwargs):
        """Send a message to a specific device

        Any extra keyword args will be passed through to the underlying sender
        implementation.

        Note:
            if neither device or device_id is specified, this will not raise an
            error!

        Args:
            category (str): Message category. This is implementation specific,
                but will be something like 'event', 'state_update', etc.
            body (dict): Body of message to send
            device (Device, optional): Device to send for
            device_id (str, optional): Device id to load and send for
            incoming_message (Message, optional): If given, the Device
                associated with that Message will be used to send to.
        """
        device = resolve_device(device, device_id, incoming_message)

        if not device:
            return # Warning message sent in _resolve_device_args

        device_type = device.product.iot_name
        self.interface.send_message(category, body, device_id=device.get_iot_id(),
                                    device_type=device_type)

    def as_device(self, category, body, device=None, device_id=None,
            incoming_message=None, **kwargs):
        """Send a message imitating a specific device.

        See to_device documentation for meanings of arguments.
        """
        device = resolve_device(device, device_id, incoming_message)

        if not device:
            return # Warning message sent in _resolve_device_args

        device_type = device.product.iot_name
        self.interface.send_as_device(category, body, device_id=device.get_iot_id(),
                                    device_type=device_type)


def resolve_device(device=None, device_id=None, incoming_message=None):
    """Given a variety of possible things to get the device_id from, return the
    'most specific' one. The order of 'specificity' is defined as:

    1. incoming_message.device
    2. device
    3. device_id

    Args:
        device (Device, optional): Device object
        device_id (str, optional): Device id
        incoming_message (Message, optional): zconnect Message

    Returns:
        Device: device object
    """
    if incoming_message:
        incoming_message_device = incoming_message.device
    else:
        incoming_message_device = None

    if device:
        given_device = device
    else:
        given_device = None

    if incoming_message_device:
        if device_id:
            logger.warning("device_id was given as well as incoming_message - device_id will be ignored")
        if given_device:
            logger.warning("device was given as well as incoming_message - device will be ignored")

        return incoming_message_device
    elif given_device:
        if device_id:
            logger.warning("device_id was given as well as device - device_id will be ignored")

        return given_device
    elif device_id:
        Device = apps.get_model(settings.ZCONNECT_DEVICE_MODEL)
        device = Device.objects.filter(pk=device_id).get()
        return device
    else:
        logger.warning("Unable to resolve device with given arguments")


class SenderSingleton:
    """ Singleton for message sender object
    """
    instance = None

    def __new__(cls):
        if not cls.instance:
            cls.instance = Sender()

        return cls.instance


def get_sender():
    """ Get singleton for watson sender

    Returns:
        SenderSingleton: global sender object
    """
    sender_settings = dict(zsettings.SENDER_SETTINGS)

    # only connect if there are settings
    if not sender_settings:
        logger.warning("Skipping watson IoT connection because there's no " \
                       "connection details")
        client = None
    else:
        client = SenderSingleton()

    return client
