from itertools import groupby
import logging

from django.conf import settings
from django.db import models

from zconnect._models.base import ModelBase
from zconnect.models import Product
from zconnect.zc_billing.util import BillingPeriod, next_bill_period

logger = logging.getLogger(__name__)


CURRENCIES = [
    ("USD", "USD"),
    ("GBP", "GBP"),
    ("EUR", "EUR"),
]


BILLING_PERIODS = [
    ("WEEKLY", BillingPeriod.weekly),
    ("MONTHLY", BillingPeriod.monthly),
    ("YEARLY", BillingPeriod.yearly),
]


class BillGenerator(ModelBase):

    """Specified how bills are created

    Taking into account things like the type of device and how often bills
    should be created

    Attributes:
        active_from_date (datetime): When billing was first activated
        cancelled_at (datetime): When billing was cancelled (if it was
            cancelled)
        currency (str): Billing currency
        enabled (bool): Whether this billing is active
        period (str): billing period - not in days, this is 'monthly', 'weekly',
            and 'yearly'
        rate_per_device (str): Amount to charge per device per 'period'
    """

    enabled = models.BooleanField(default=True)
    rate_per_device = models.IntegerField()
    currency = models.CharField(max_length=3, choices=CURRENCIES)
    cancelled_at = models.DateTimeField(null=True)
    period = models.CharField(max_length=20, choices=BILLING_PERIODS)
    active_from_date = models.DateTimeField()

    organization = models.OneToOneField(
        "organizations.Organization",
        models.PROTECT,
        # null=True,
        related_name="billed_by",
    )


class Bill(ModelBase):

    """Represents a single 'invoice'/bill that has been created using the
    BillGenerator

    Because the number of devices that an org is being billed for might change
    from one period to another, store a reference between each device that was
    being billed for this bill via a m2m field

    Attributes:
        paid (bool): Whether this has been paid or not
        period_end (datetime): End of period this bill applies to
        period_start (datetime): Start of period this bill applies to
        devices (list(Device)): devices active for this bill period
        generated_by (BillGenerator): Generator for this bill
    """

    paid = models.BooleanField(default=False)
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    # (fields.W340) null has no effect on ManyToManyField
    devices = models.ManyToManyField(settings.ZCONNECT_DEVICE_MODEL) #, null=False)

    generated_by = models.ForeignKey(BillGenerator, models.PROTECT,
                                     related_name="bills")

    class Meta:
        ordering = ('-period_end', )
        get_latest_by = 'period_end'

    @property
    def amount(self):
        return self.generated_by.rate_per_device*self.devices.all().count()

    @property
    def next_period_end(self):
        return next_bill_period(self.generated_by.active_from_date,
                                self.generated_by.period, self.period_end)[1]

    @property
    def organization(self):
        return self.generated_by.organization

    @property
    def currency(self):
        return self.generated_by.currency

    @property
    def devices_by_product(self):
        """ Get devices listed on this bill, grouped by product. """

        # Order by product first...
        by_product = self.devices.all().order_by("product_id")

        def pid(device):
            return device.product_id

        # Already grouped by product, so we can just do a groupby() immediately
        return [{
            "product": Product.objects.get(pk=product_id),
            "devices": devices
        } for  product_id, devices in groupby(by_product, pid)]
