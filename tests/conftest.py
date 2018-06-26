from unittest.mock import patch

from mockredis import mock_strict_redis_client
import pytest

from zconnect.testutils.fixtures import *  # noqa


# Always mock redis
@pytest.fixture(autouse=True)
def fake_get_redis():
    with patch("zconnect.tasks.get_redis", return_value=mock_strict_redis_client()), \
    patch("zconnect.util.rate_limiter.get_redis", return_value=mock_strict_redis_client()):
        yield


@pytest.fixture(autouse=True, scope="session")
def fix_load_settings():
    import django
    from django.conf import settings
    from zconnect.pytesthook import get_test_settings

    test_settings = get_test_settings()

    try:
        settings.configure(**test_settings)
    except RuntimeError:
        # If it's already set up, this is going to be run as part of another
        # app. This will test that the app settings actually work with what
        # zconnect expects, but it's bit of a hack
        pass
    else:
        # Otherwise set up 'test' settings
        django.setup()
