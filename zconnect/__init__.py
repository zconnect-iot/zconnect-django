__version__ = "0.0.1"

# FIXME
# celery docs:
# http://docs.celeryproject.org/en/latest/django/first-steps-with-django.html
# suggest doing this, but it doesn't work because the apps aren't finished
# loading by the time it imports the tasks etc. (which in turn import models).
# Need to either import all models INSIDE tasks, or start the celery app a
# different way.
# from ._tasks import app as celery_app

default_app_config = 'zconnect.apps.ZconnectAppConfig'


class register_setting:
    """Defines a setting which will be dynamically read when loaded
    """

    def __init__(self, setting):
        self.setting = setting

    def __set__(self, obj, val):
        raise AttributeError("{:s} settings cannot be overwritten".format(type(self)))

    def __delete__(self, obj):
        raise AttributeError("{:s} settings cannot be deleted".format(type(self)))

    def __get__(self, obj, klass=None):
        if klass is None:
            klass = type(obj)

        from django.conf import settings
        overridden_settings = getattr(settings, "ZCONNECT_SETTINGS", {})

        return overridden_settings.get(self.setting, {})


class zsettings:
    LISTENER_SETTINGS = register_setting("LISTENER_SETTINGS")
    SENDER_SETTINGS = register_setting("SENDER_SETTINGS")
    ARCHIVE_PRODUCT_AGGREGATIONS = register_setting("ARCHIVE_PRODUCT_AGGREGATIONS")
