from django.apps import AppConfig, apps
from django.conf import settings


class ZconnectAppConfig(AppConfig):
    name = 'zconnect'

    def ready(self):
        from actstream import registry
        registry.register(apps.get_model(settings.ZCONNECT_DEVICE_MODEL))
