from collections import deque
import functools
import importlib
from itertools import islice, zip_longest

from django.apps import apps
from django.conf import settings


def nested_getattr(obj, attr, default=None):
    def _getattr(obj, name):
        return getattr(obj, name, default)

    return functools.reduce(_getattr, [obj]+attr.split('.'))


# itertools recipes
def consume(n, it):
    """Advance the iterator n-steps ahead. If n is none, consume entirely."""
    # Use functions that consume iterators at C speed.
    if n is None:
        # feed the entire iterator into a zero-length deque
        deque(it, maxlen=0)
    else:
        # advance to the empty slice starting at position n
        next(islice(it, n, n), None)


def take(n, it):
    """Return first n items of the iterable as an iterator"""
    return islice(it, n)


def group(n, it, fillvalue=None):
    """Return elements of iterable in groups of n"""
    ntimes = [iter(it)] * n
    return zip_longest(*ntimes, fillvalue=fillvalue)


def load_device(device_id):
    """Load device by id
    """
    Device = apps.get_model(settings.ZCONNECT_DEVICE_MODEL)
    return Device.objects.filter(id=device_id).first()


def load_from_module(item):
    """Load something from a module like django

    Args:
        item (str): Item in a module, separated by dots - eg
            "package.module.MyClass"

    Returns:
        object: whatever was loaded

    Raises:
        ImportError: No such module
        AttributeError: No such item in module
    """
    mod_name, _, cls_name = item.rpartition(".")
    module = importlib.import_module(mod_name)
    cls = getattr(module, cls_name)

    return cls
