import datetime
import inspect
from itertools import chain
import json
import re
import time

from django.db.models.fields import DateTimeField
from django.db.models.fields.files import FileField, ImageField
from django.db.models.fields.related import ManyToManyField
import jsonfield
import pytest

# pylint: disable=attribute-defined-outside-init


class ContextTimer:
    """ Simple timer used as context manager """

    def __enter__(self):
        self.start = time.clock()
        return self

    def __exit__(self, *args):
        self.end = time.clock()
        self.interval = self.end - self.start


def get_full_route(path_params, route):
    """ Takes route and path parameters and formats into url

    Route can be something like /{user_id}/stats, in which case
    path_params should be a dict containing a value for user_id like
    {"user_id": "dave"}

    If there are no path parameters, just returns the route

    Args:
        path_params (dict): Dictionary of path parameters
        route (str): route with possible path parameters in

    Returns
        str: formatted path
    """

    if path_params is None:
        path_params = {}

    if any(i not in route for i in path_params):
        extra = set(path_params) - set(re.finditer("{[^}]+}", route))
        pytest.fail("Unexpected path parameters passed - {}".format(extra))

    try:
        return route.format(**path_params)
    except KeyError as e:
        pytest.fail("Missing key for route '{}': {}".format(route, e))


def model_to_dict(instance, fields=None, exclude=None, date_to_strf=None):
    """
    Why is `__fields` in here?
        it holds the list of fields except for the one ends with a suffix '__[field_name]'.
        When converting a model object to a dictionary using this method,
        You can use a suffix to point to the field of ManyToManyField in the model instance.
        The suffix ends with '__[field_name]' like 'publications__name'
    """
    opts = instance._meta
    data = {}

    __fields = list(map(lambda a: a.split('__')[0], fields or []))
    #pylint: disable=too-many-nested-blocks
    for f in chain(opts.concrete_fields, opts.many_to_many):
        is_editable = getattr(f, 'editable', False)

        if fields and f.name not in __fields:
            continue

        if exclude and f.name in exclude:
            continue

        if isinstance(f, ManyToManyField):
            if instance.pk is None:
                data[f.name] = []
            else:
                qs = f.value_from_object(instance)
                if qs:
                    qs = [item.pk for item in qs]
                data[f.name] = qs

        elif isinstance(f, DateTimeField):
            date = f.value_from_object(instance)
            if date != None:
                data[f.name] = date_to_strf(date) if date_to_strf else date.isoformat()
            else:
                data[f.name] = None
        elif isinstance(f, ImageField):
            image = f.value_from_object(instance)
            data[f.name] = image.url if image else None

        elif isinstance(f, FileField):
            file = f.value_from_object(instance)
            data[f.name] = file.url if file  else None

        elif isinstance(f, jsonfield.JSONField):
            raw = f.value_from_object(instance)
            data[f.name] = raw if isinstance(raw, dict) else json.loads(raw)

        elif is_editable:
            data[f.name] = f.value_from_object(instance)

    # Just call an instance's function or property from a string with the
    # function name in `__fields` arguments.
    funcs = set(__fields) - set(list(data.keys()))
    for func in funcs:
        obj = getattr(instance, func)
        if inspect.ismethod(obj):
            data[func] = obj()
        else:
            data[func] = obj
    return data


def assert_successful_edit(testclient, fakemodel, path_params, post_key, post_value, serializer=None):
    """Update one field"""
    # As expected
    expected = {
        "status_code": 200,
        "body": serializer(fakemodel).data if serializer else model_to_dict(fakemodel)
    }
    testclient.get_request_test_helper(expected, path_params=path_params)

    after_update_model = serializer(fakemodel).data if serializer else model_to_dict(fakemodel)
    after_update_model[post_key] = post_value

    post_body = {
        post_key: post_value,
    }
    expected = {
        "status_code": 200,
        "body": after_update_model
    }

    # Do not test the updated_at value
    if 'updated_at' in after_update_model:
        after_update_model['updated_at'] = None

    testclient.patch_request_test_helper(post_body, expected, path_params=path_params)

    # Expect it to change
    expected = {
        "status_code": 200,
        "body": after_update_model
    }
    testclient.get_request_test_helper(expected, path_params=path_params)


def weeks_ago(n_weeks):
    """Lazily returns a datetime from n_weeks ago"""
    def inner():
        return datetime.datetime.utcnow() - datetime.timedelta(weeks=n_weeks)

    return inner
