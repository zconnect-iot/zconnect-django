from django.db import models
import semver

from .base import ModelBase
from .mixins import EventDefinitionMixin


class Product(EventDefinitionMixin, ModelBase):
    """Defines a type of product

    Note that both the state serializer and deserializer can be blank. Some
    products might never have to serialize the state and some might not care
    about verifying the schema when deserializing it (though this is highly
    inadvisable).

    Attributes:
        battery_voltage_critical (float): What voltage of battery is considered
            critical for this device (eg, possibly used to trigger a push
            notification to the owner)
        battery_voltage_full (float): voltage of battery for this product which
            is considered 'full'
        battery_voltage_low (float): What volage of battery is considered 'low'
            for device
        iot_name (str): Watson IoT device type
        manufacturer (str): Name of manufacturer
        name (str): Name of device
        periodic_data (bool, True): Whether this device can give periodic data
        periodic_data_interval_long (int, 21600): 'long' periodic data interval
            for summary - default 6 hours
        periodic_data_interval_short (int, 120): 'short' interval
        periodic_data_num_intervals_long (int, 112): ???
        periodic_data_num_intervals_short (int, 180): ???
        periodic_data_retention_short (int): How long to retain high resolution
            data for. Don't want to keep it forever or it will use a lot of data
            in the database
        previous_version (Product): A previous version of this product, if there
            was one
        server_side_events (bool, False): Whether events should be triggered on
            the server side for this product.
        sku (str): SKU of product
        support_url (str): URL of help for this product
        tags (list(str)): generic tags for product
        url (str): Product (or manufacturer) homepage
        version (str): Release of the product, hopefully a semver...?

        state_serializer_name (str): location of serializer to convert state
            from zconnect.DeviceState to serialization format (json, msgpack,
            ...)
    """
    name = models.CharField(max_length=100)
    iot_name = models.CharField(max_length=100)
    sku = models.CharField(max_length=100, blank=True)
    manufacturer = models.CharField(max_length=50)
    url = models.CharField(max_length=200, blank=True)
    support_url = models.CharField(max_length=200, blank=True)

    state_serializer_name = models.CharField(max_length=200, blank=True)

    version = models.CharField(max_length=50)
    previous_version = models.ForeignKey("Product", models.CASCADE, blank=True, null=True)

    periodic_data = models.BooleanField(default=True)

    # Periodic data document size settings - doesn't normally need
    # changing!
    periodic_data_interval_short = models.IntegerField(default=120)
    periodic_data_num_intervals_short = models.IntegerField(default=180)
    periodic_data_interval_long = models.IntegerField(default=6 * 3600)
    periodic_data_num_intervals_long = models.IntegerField(default=112)

    periodic_data_retention_short = models.IntegerField(
        default=3600 * 24 * 30)  # 30 days in seconds

    server_side_events = models.BooleanField(default=False)

    battery_voltage_full = models.FloatField()
    battery_voltage_critical = models.FloatField()
    battery_voltage_low = models.FloatField()

    @property
    def periodic_data_doc_period_short(self):
        return self.periodic_data_interval_short * \
            self.periodic_data_num_intervals_short

    @property
    def periodic_data_doc_period_long(self):
        return self.periodic_data_interval_long * \
            self.periodic_data_num_intervals_long

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["manufacturer"]


class ProductPreprocessors(ModelBase):
    """preprocessors to run on sensor data

    Attributes:
        preprocessor_name (str): function name of preprocessors
        product (product): related product
    """

    product = models.ForeignKey("Product", models.CASCADE, related_name="preprocessors", blank=False)
    preprocessor_name = models.CharField(max_length=100)


class ProductTags(ModelBase):
    """Tags on the product

    Attributes:
        product (product): related product
        tag (str): tag
    """

    product = models.ForeignKey("Product", models.CASCADE, related_name="tags", blank=False)
    tag = models.CharField(max_length=20)


class ProductFirmware(ModelBase):
    """Stores information about a device firmware version, which
    let's us track updates.

    Note:
        fw_version and fw_version_string cannot be modified in the same
        transaction

    Attributes:
        download_url (str): URL to fetch firmware from
        fw_version (SemVer): Semantic version of firmware, as a semver
        fw_version_string (str): semantic version as a string
        product (Product): Product this firmware is used for
    """

    # Don't care about keeping productfirmware after it's deleted
    product = models.ForeignKey("Product", models.CASCADE, blank=False)
    download_url = models.CharField(max_length=200)

    major = models.IntegerField()
    minor = models.IntegerField()
    patch = models.IntegerField()
    prerelease = models.CharField(max_length=20, blank=True)
    build = models.CharField(max_length=20, blank=True)

    def fw_version_string(self):
        return semver.format_version(
            self.major, self.minor, self.patch, prerelease=self.prerelease, build=self.build
        )

    def download_update(self):
        """ Download the fw update from the object storage provider and return
        bytes

        Gets the firmware from watson object storage

        Returns:
            file: a file like object with a read method
        """
        raise NotImplementedError
        # FIXME
        # abstract away
        # from zconnect.util.watson_object_storage import download_fw_update
        # return download_fw_update(self)
