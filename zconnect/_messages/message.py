import datetime
import logging

from django.apps import apps
from django.conf import settings
from rest_framework import serializers
from rest_framework.exceptions import ValidationError as DRFValidationError

from zconnect.registry import get_message_handlers, load_from_file
from zconnect.util import exceptions

from .sender import get_sender

logger = logging.getLogger(__name__)


class DevicePKField(serializers.Field):
    """serialize/deserialize device pk for messages"""
    def to_representation(self, obj):
        return obj.pk

    def to_internal_value(self, data):
        Device = apps.get_model(settings.ZCONNECT_DEVICE_MODEL)

        if isinstance(data, Device):
            return data
        else:
            device_pk = data
            device = Device.objects.get(pk=device_pk)
            return device


class MessageSerializer(serializers.Serializer):
    """Serializes a Message object to a dict

    See documentation for Message on what these fields mean
    """
    category = serializers.CharField(required=True)
    body = serializers.JSONField(required=True)
    device = DevicePKField(required=True)
    timestamp = serializers.DateTimeField(required=True)


class Message:

    def __init__(self, category, body, device, timestamp=None):
        """ A standard message object which has all the necessary information
            to construct an event/message in most brokers, e.g. Watson IoT

        Args:
            category (string): The category/type of message which controls what handler(s)
                                will respond to it
            body (dict): A dict which has been decoded by the broker interface.
            device (zconnect.models.Device): The device which this corresponds to.
            timestamp (datetime, optional): if passed in, must be a datetime, or it will be
                            set to the current time.
        """
        self.category = category
        self.body = body
        self.device = device
        ts = timestamp or datetime.datetime.now()
        self.timestamp = ts.replace(tzinfo=None)

    def __repr__(self):
        return "Message(\
            category={}\
            timestamp={}\
            device={}\
            body={}\
        )".format(self.category, self.timestamp, self.device.id, self.body)

    def as_dict(self):
        return MessageSerializer(instance=self).data

    @classmethod
    def from_dict(cls, d):
        serializer = MessageSerializer(data=d)

        try:
            serializer.is_valid(raise_exception=True)
        except DRFValidationError as e:
            raise exceptions.BadMessageSchemaError("Invalid message data") from e

        return cls(**serializer.validated_data)

    def send_to_device(self):
        """Send this message to the associated device"""
        sender = get_sender()
        sender.to_device(
            self.category,
            self.body,
            device=self.device,
        )


class MessageProcessor():

    def __init__(self, message_handlers=False):

        if not message_handlers:
            load_from_file("handlers")
            message_handlers = get_message_handlers()
        self.message_handlers = message_handlers

    def process(self, message):
        handlers = self.message_handlers.get(message.category, [])

        if not handlers:
            logger.error("No handler for '%s' messages", message.category)
            logger.debug(message.body)
            return

        for handler in handlers:
            try:
                logger.debug("Recieved message: %r", message)
                handler(message, self)
            except Exception: # pylint: disable=broad-except
                logger.exception("Exception raised during processing of "
                                 "event %s", message)


class MessageProcessorSingleton:
    """ Singleton for message processor object
    """
    instance = None

    def __new__(cls):
        if not cls.instance:
            cls.instance = MessageProcessor()

        return cls.instance


def get_message_processor():
    """ Get singleton for MessageProcessor

    Returns:
        MessageProcessor: a message processor
    """
    client = MessageProcessorSingleton()

    return client
