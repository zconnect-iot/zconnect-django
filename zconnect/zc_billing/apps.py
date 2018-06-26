from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class BillingAppConfig(AppConfig):
    name = "zconnect.zc_billing"
    verbose_name = _("Zconnect Billing Module")
