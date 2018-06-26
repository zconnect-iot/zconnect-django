from django.conf import settings
from zconnect.models import AbstractDevice


class ZCTestDevice(AbstractDevice):
    class Meta:
        ordering = ["product"]
        default_permissions = ["view", "change", "add", "delete"]
        abstract = not ("zc_test_app" in settings.INSTALLED_APPS)
