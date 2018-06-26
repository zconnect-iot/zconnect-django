import logging

from .cache import (
    _action_handlers, _activity_notifiers, _message_handlers, _preprocessors,
    _state_transition_handlers)

logger = logging.getLogger(__name__)


def _unwrap(_cache, *args, is_list=True, **kwargs):
    """Register a decorator with it's specific cache

    This will add a new mapping in the given cache with the function name
    mapping to the given value. if is_list is passed, it means that multiple
    notifiers/actions/etc can be registered with the same name. If false, it
    will raise an error if you try to register something with the same name as
    has already been defined

    Args:
        _cache (): One of the things above (_notifiers, _preprocessors, etc)
        is_list (bool): Whether another thing with the same name can be
            registered

    Returns:
        func: the original function or a decorator (if called with kwargs)
    """

    opts = kwargs

    def insert_into_cache(func):
        name = opts.pop("name", func.__name__)

        if is_list:
            try:
                _cache[name].append(func)
            except KeyError:
                _cache[name] = [func]
        else:
            if name in _cache:
                handler_cache_name = opts.pop("cache_name", "<unknown>")
                logger.error("'%s' already registered in %s cache", name, handler_cache_name)
                raise Exception(
                        "Tried to add a {} with the same name ({})"
                        .format(handler_cache_name, name))
            _cache[name] = func

        return func

    if kwargs:
        return insert_into_cache

    if len(args) == 1:
        func = args[0]
        if callable(func):
            return insert_into_cache(func)
        raise TypeError('argument 1 to @<decorator>() must be a callable')
    else:
        raise TypeError(
            '@<decorator>() takes exactly 1 argument ({0} given)'.format(
                sum([len(args), len(kwargs)])))


def preprocessor(*args, **kwargs):
    """Register a `preprocessor` for time series data.

    `preprocessors` are used with timeseries data and are designed to allow
    enriching or transforming incoming data from a `periodic` message. these
    can be per device/product etc (by inspecting the `device` argument to the
    handler).

    Preprocessors act directly on the `data` dictionary argument, in order to
    add/remove/alter keys.

    Any key which is added by a pre-processor will only be saved if it is also
    a valid `sensor` name, as defined on the product.

    ..code-block:: python

        # or @preprocessor(name="another_name_for_ac_preprocessor")
        @preprocessor
        def process_ac(data, device=False, ts_cls=False):

    The arguments to the handler will be:
    * `data` - the incoming timeseries packet. This may have been altered by previous
                time series preprocessor handlers
    * `device` - The device which is being acted upon.
    * `tc_cls` - The cls which is being used to save the data. This may be useful if
                    the preprocessing doesn't need to happen on the archived version
                    or vice-versa.

    The return value is ignored.

    `device` and `ts_cls` are kwargs and may be left out of the function signature.
    """
    logger.debug("Adding preprocessor from %s", args)
    return _unwrap(_preprocessors, *args, **kwargs,
                    is_list=False, cache_name="preprocessor")


def activity_notifier_handler(*args, **kwargs):
    """ Register a `notifier_handler`.

    Notfiers are used to send information from the creation of a new
    activity to a user.

    This may include:
    * emails
    * SMS
    * push notifications
    * webhooks
    * slack etc

    ..code-block:: python

        # @activity_notifier_handler has an optional `name` which should correspond to
        # the `type` field on the `ActivitySubscription`s.
        @activity_notifier_handler(name="action_name")
        def activity_notifier_handler(user, action, device=False, \
            organization=False, activity_stream=False):

    The arguments to the handler are:
    * `user` - The user to notify
    * `action` - The newly created action which has generated the alert
    * `device` - The device associated with the action (for convienience)
    * `organization` - An optional organization if the device is part of an
                        organization
    * `activity_stream` - A queryset for relevant activity actions which may be
                            used in the notification.

    The return value should be a boolean for success. This will be stored on the activity to
    mark if it was successful.

    Exceptions will be caught, but cause a failure to be recorded.

    """
    logger.debug("registering notifier from %s", args)
    return _unwrap(_activity_notifiers, *args, **kwargs,
                    is_list=False, cache_name="activity_notifier")


def action_handler(*args, **kwargs):
    """ Register an `action_handler`.

    Action handlers are used to process `actions` defined on an `event_definition`.
    This allows you to add funcionality which should happen in response to conditions
    from events happening.

    Examples of the kinds of actions you may want are:
    1. Enabling/Disabling devices depending on external conditions. In this case the action
        handler would be used to perform the enabling/disabling
    2. Generation of Actions on the Activity stream - this is done to track what's
        happened to a particular device over time.
    3. Automatic actions at certain times of day

    Action handlers should be decorated and have the function signature below:

    ..code-block:: python

        # @action_handler has an optional `name` which should correspond to
        # the name of the action in the event_definition.actions dict.
        @action_handler(name="action_name")
        def action_handler(message, listener=False, action_args=False, event_def):

    The arguments to the action handler will be:
    * `message` - The incoming event Message object, which will have the category `event`.
    * `listener` - The listener which recieved the message. Can be used if
                    messages need to be sent in response.
    * `action_args` - A convienience object which contains the arguments stored in the
                      event_def. This saves looking them up from the event_def
    * `event_def` - The complete event definition which triggered this action.

    The return value is ignored. Exceptions will be caught, however this will cause the
    `Event` to have `success=False` set on it.

    `listener`, `action_args` and `event_def` are kwargs, and as such can be left out
    of the function signature if they're not needed for the action being implemented.

    """
    logger.debug("registering action_handler from %s", args)
    return _unwrap(_action_handlers, *args, **kwargs,
                    cache_name="action")


def state_transition_handler(*args, **kwargs):
    """
        TODO: decide on how this works and document.
    """
    logger.debug("registering state_transition_handler from %s", args)
    return _unwrap(_state_transition_handlers, *args, **kwargs,
                    cache_name="state_transition")


def message_handler(*args, **kwargs):
    """ Regsiter a `message_handler`.

    Messages (`zconnect._messages.message.Message`) are a how ZConnect represents
    data which is being passed around the zconnect system - normally this will be
    from an MQTT server or AMQP broker, however the abstraction allows for internal
    use - e.g. for triggering async actions by putting messages on a celery queue etc.

    handlers are registered against a category name (the `name` argument to the decorator).
    upon registering, when a message of that event category is recieved it will be
    passed to the handler.

    ..code-block:: python

        # @message_handler has an optional `name` which should correspond to
        # the name of the category of message which this handles.
        @message_handler(name="action_name")
        def message_handler(message, listener):

    The arguments to the action handler will be:
    * `message` - The incoming event Message object, which will have the category `event`.
    * `listener` - The listener which recieved the message. Can be used if
                    messages need to be sent in response.

    The return value is ignored. Exceptions will be caught and logged.
    """
    logger.debug("registering message_handler from %s", args)
    return _unwrap(_message_handlers, *args, **kwargs,
                    cache_name="message_handler")
