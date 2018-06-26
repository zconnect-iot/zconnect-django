from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class TimeseriesAppConfig(AppConfig):
    name = "zconnect.zc_timeseries"
    verbose_name = _("Zconnect Timeseries Data Module")
