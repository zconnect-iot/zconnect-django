import logging

from rest_auth.utils import import_callable
from rest_framework import serializers
from rest_framework.exceptions import ValidationError as DRFValidationError

from zconnect.util import exceptions

logger = logging.getLogger(__name__)


def get_product_state_serializer(product):
    """Get serializer that can be used to validate a device's state update
    messages. See documentation for get_state_serializer_cls for information on
    args etc.
    """

    # Use this by default
    state_serializer_cls = serializers.JSONField

    if product:
        serializer_name = product.state_serializer_name
        if not serializer_name:
            logger.warning("Product passed with no explicit state_serializer_name - using JSONField which will match ANY data")
        else:
            try:
                state_serializer_cls = import_callable(serializer_name)
            except (ValueError,ImportError) as e:
                raise exceptions.BadMessageSchemaError("Error loading schema verifier from '{}'".format(serializer_name)) from e

    else:
        logger.info("No product - using JSONField to validate input")

    return state_serializer_cls


def get_state_serializer_cls(product=None):
    """Given the 'actual' serializer for the state of a device (which will be
    based on the Product), return a serializer that can verify the whole state
    update object.

    This has to recreate it because the inner serializer is going to change
    based on the device/product.

    State should be like this:

    .. code-block:: python

        {
            "state": {
                "reported": {
                    "abc": 123,
                    ...
                }
            }
        }

    Todo:
        This could be decorated with functools.lru_cache to stop it recreating
        the serializers every time, this has been left out for the time being
        for debugging

    Args:
        product (zconnect.Product, optional): product which will define a
            serializer to validate a state update. If you just want to validate
            a generic message, pass None (or no argument) to cause it to use a
            serializers.JSONField, which will validate ANY json data.

    Returns:
        serializers.Serializer: new serializer to validate a state update
    """

    state_serializer_cls = get_product_state_serializer(product)

    class InnerSerializer(serializers.Serializer):
        """Serializer representing a device reporting a state change.

        Other fields might be added in future, currently we just expect this key
        """
        reported = state_serializer_cls(required=True)

    class OuterSerializer(serializers.Serializer):
        """The top level of a state document. This serializer should be used to
        validate the 'unwrapped' messages from whatever broker library is being
        used.

        For example, in IBM messages this will actually be wrapped in a message like
        this:

        .. code-block:: python

            {
                "category": "event",
                "d": {
                    "state": {
                        ...
                    }
                }
            }

        but it is unwrapped and we should just get the "state"
        """
        state = InnerSerializer(required=True)

    return OuterSerializer


def verify_message_schema(message):
    """Given a zconnect state Message, verify that it is in the right format

    First of all it expectes a top level 'state' key. This is currently the only
    top level key - there may be more in future (tags, metadata, etc).

    This state key should then have the 'reported' state from the device, which
    should either by be a response from a requested state update from the
    server, a periodic update of state, or a signal that the device state has
    changed for some reason.

    This 'reported' key is then passed through to a product-specific function
    which should check that the message is in the correct schema. If it isn't, a
    message will be published to the device to indicate that it has sent the
    message in the wrong format (and should be handled or logged on the device
    somehow).

    Args:
        message (Message): zconnect message

    Raises:
        BadMessageSchemaError: If the message format was invalid
    """

    serializer_cls = get_state_serializer_cls(message.device.product)

    # Message.body is a dict already
    serializer = serializer_cls(data=message.body)

    try:
        serializer.is_valid(raise_exception=True)
    except DRFValidationError as e:
        raise exceptions.BadMessageSchemaError("Invalid message schema") from e
    except Exception as e:
        raise exceptions.BadMessageSchemaError("Unexpected exception verifying message schema") from e
