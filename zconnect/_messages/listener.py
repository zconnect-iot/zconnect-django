import logging

import gevent

from zconnect import zsettings
from zconnect.registry import get_message_handlers, load_from_file
from zconnect.util import exceptions
from zconnect.util.general import load_from_module
from zconnect.util.rate_limiter import RateLimit, TooManyRequests

logger = logging.getLogger(__name__)


class Listener:

    """Generic message listener

    This provides an abstract interface to whatever listener backend is being
    used

    Attributes:
        rl (RateLimiter): Class which can be used as a context manager to rate
            limit messages from certain devices
    """

    # Sets the rate limiter class
    rl = RateLimit

    def __init__(self, message_handlers):
        """ Should only be called from listener process

        Args:
            message_handlers (dict): Dictionary of name: list(handler), mapping
                what handlers should be called when a certain event is
                triggered
        """
        listener_settings = dict(zsettings.LISTENER_SETTINGS)
        cls_name = listener_settings.get("cls", "zconnect.messages.IBMInterface")
        interface_class = load_from_module(cls_name)
        self.broker_interface = interface_class(listener_settings)

        self.message_handlers = message_handlers
        self.rate_limits = listener_settings['worker_events_rate_limits']
        self.rate_limit_period = listener_settings['rate_limit_period']

    def _message_callback(self, message):
        """ Given a zconnect message, send it to all the message handlers that
            are listening to that message's category

        Args:
            message (Zconnect message object): The incoming message
        """
        handlers = self.message_handlers.get(message.category, [])

        if not handlers:
            logger.error("No handler for '%s' messages", message.category)
            logger.debug(message.body)
            return

        for handler in handlers:
            try:
                # Apply rate limiting by the message name defined in the
                # config
                logger.debug("Recieved message: %r", message)
                if message.category in self.rate_limits:
                    with self.rl(message.category, message.device.id,
                                 self.rate_limits[message.category],
                                 expire=self.rate_limit_period):
                        handler(message, self)
                else:
                    handler(message, self)

            except TooManyRequests:
                logger.warning("Rate limited device id %s with event type %s",
                               message.device.id, message.name)

            except exceptions.WorkerError:
                logger.exception("Worker error raised during processing of "
                                 "event %s", message)

            except Exception: # pylint: disable=broad-except
                logger.exception("Unexpected exception raised during processing of "
                                 "event %s", message)

    def subscribe_to_events(self):
        self.broker_interface.subscribe_to_events(self._message_callback)


class MessageListenerGreenlet(gevent.Greenlet):
    """ Handles all triggered events

    Loads:

        - notifiers
        - action handlers, requires notifiers
        - state transition handlers
        - event handlers
        - preprocessors

    Then starts the watson client to wait for these events
    """

    def __init__(self):
        """ Load handlers from all files into _message_handlers,
            then load that list and pass it to the Listener constructor
        """

        load_from_file("handlers")
        message_handlers = get_message_handlers()
        self.client = Listener(message_handlers)

        super().__init__()

    def _run(self): # pylint: disable=method-hidden
        logger.info("Starting message listener")

        self.client.subscribe_to_events()

        while 1:
            # The watson client just starts a paho thread in the background
            # which waits for messages - we just sleep here and let that thread
            # do it's thing
            gevent.sleep(83)


def get_listener():
    """ Start the listener in a gevent loop
    """
    w = MessageListenerGreenlet()

    return w
