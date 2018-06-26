import logging

from celery.loaders.base import autodiscover_tasks
from django.apps import apps

logger = logging.getLogger(__name__)


def load_from_file(modname):
    """Load plugins djang-style rather than with plugins

    Reuse celery util which just loads the 'preprocessors' module from all
    INSTALLED_APPS.
    """

    appnames = [config.name for config in apps.get_app_configs()]
    # This will run all decorated function automatically
    autodiscover_tasks(appnames, modname)


def get_action_handlers(name):
    """Load all action handlers that will be triggered by the given name

    Args:
        name (str): associated trigger key for action handlers

    Returns:
        list: List of all action handlers that should be triggered by the given
            name
    """
    from .cache import _action_handlers
    logger.debug("Available action handlers: %s", _action_handlers)
    return _action_handlers.get(name)


def get_activity_notifier_handler(name):
    """Get notification handlers for given  name

    Args:
        name (str): associated trigger key for notifiers

    Returns:
        list: List of notification handlers for given name
    """
    from .cache import _activity_notifiers
    logger.debug("Available activity notifiers handlers: %s",
                    _activity_notifiers)
    return _activity_notifiers.get(name)


def get_preprocessor(name):
    """ Try to get a preprocessor by name from preprocessors loaded

    Args:
        name (str): name of preprocessor

    Returns:
        function: preprocessor with signature (data, device, ts_cls), or None if
            that preprocessor doesn't exist
    """

    from .cache import _preprocessors
    logger.debug("Available preprocessors: %s", _preprocessors)
    return _preprocessors.get(name)


def get_message_handlers():
    """Get all message handlers.

    Returns:
        dict: mapping of event key=>action handler
    """
    from .cache import _message_handlers
    logger.debug("Available handlers: %s", _message_handlers)
    return _message_handlers
