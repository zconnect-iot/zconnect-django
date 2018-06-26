from django.conf import settings
from rest_auth.utils import import_callable

from zconnect.testutils.util import model_to_dict


def paginated_body(results):
    """Just return a simple paginated result body based on results

    this does not take next/previous into account - any tests using that should
    specifically set values in the expected body

    Args:
        results (list): Expected results

    Returns:
        dict: previous/next will be None, count is the number of results
    """
    if not isinstance(results, list):
        raise TypeError("Input should be a list")

    return {
        "results": [dict(r) for r in results],
        "count": len(results),
        "previous": None,
        "next": None,
    }


def expect_model(status, model, serializer=None):
    return {
        "status_code": status,
        "body": serializer(model).data if serializer else model_to_dict(model)
    }

def expect_detail(status, detail):
    return {
        "status_code": status,
        "body": {
            "detail": detail
        }
    }

def expect_list(status, results_list):
    return {
        "status_code": status,
        "body": paginated_body(results_list)
    }


def device_to_dict(device):
    """convert device to dictionary

    note:
        if the keys are different then the error message given by tavern might be
        a bit confusing. comparing a dict to an ordereddict (as returned by the
        serializer) works, but if a key is different then it will also complain
        about the types being different
    """

    serializer = import_callable(settings.ZCONNECT_DEVICE_SERIALIZER)
    dumped = serializer(instance=device).data
    return dumped
