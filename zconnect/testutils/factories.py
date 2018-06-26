import datetime
from io import BytesIO

from PIL import Image
from django.apps import apps
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import Group
from django.core.files import File
import factory
import factory.fuzzy
from organizations.models import Organization, OrganizationUser

from zconnect.models import (
    ActivitySubscription, DeviceState, DeviceUpdateStatus, Event, EventDefinition, Location,
    OrganizationLogo, Product, ProductFirmware, ProductPreprocessors, ProductTags, UpdateExecution)
from zconnect.zc_billing.models import Bill, BilledOrganization, BillGenerator
from zconnect.zc_timeseries.models import DeviceSensor, SensorType, TimeSeriesData

from .util import weeks_ago


class GroupFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Group
        django_get_or_create = ["name"]

    name = "zc-test-group"


class ModelBaseFactory(factory.django.DjangoModelFactory):
    created_at = factory.LazyFunction(datetime.datetime.utcnow)
    updated_at = factory.LazyFunction(datetime.datetime.utcnow)


class UserFactory(ModelBaseFactory):
    class Meta:
        model = apps.get_model(settings.AUTH_USER_MODEL)
        # pk on user
        django_get_or_create = ["username"]

    first_name = "joe"
    last_name = "seed"
    email = "joeseed@zoetrope.io"
    username = "joeseed@zoetrope.io"
    password = make_password("test_password")


class ProductFactory(ModelBaseFactory):
    class Meta:
        model = Product

    name = "Test product"
    iot_name = "testproduct123"
    manufacturer = "Zoetrope"
    version = "alpha-2"

    battery_voltage_full = 5.0
    battery_voltage_low = 3.0
    battery_voltage_critical = 1.0


class OrganizationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Organization

    name = "A Fake Organization"
    is_active = True


class OrganizationMemberFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = OrganizationUser

    is_admin = False
    user = factory.SubFactory(UserFactory)
    organization = factory.SubFactory(OrganizationFactory)


class ProductPreprocessorsFactory(ModelBaseFactory):
    class Meta:
        model = ProductPreprocessors

    product = factory.SubFactory(ProductFactory)
    preprocessor_name = 'Preprocessor'


class ProductTagsFactory(ModelBaseFactory):
    class Meta:
        model = ProductTags

    product = factory.SubFactory(ProductFactory)
    tag = 'Tag'


class DeviceFactory(ModelBaseFactory):
    class Meta:
        model = apps.get_model(settings.ZCONNECT_DEVICE_MODEL)

    product = factory.SubFactory(ProductFactory)
    last_seen = factory.LazyFunction(datetime.datetime.utcnow)
    name = "testdevice"
    fw_version = "1.2.3"


class SensorTypeFactory(ModelBaseFactory):
    class Meta:
        model = SensorType

    sensor_name = "power_sensor"
    unit = "watts"
    aggregation_type = "sum"
    product = factory.SubFactory(ProductFactory)


class DeviceSensorFactory(ModelBaseFactory):
    class Meta:
        model = DeviceSensor

    device = factory.SubFactory(DeviceFactory)
    sensor_type = factory.SubFactory(SensorTypeFactory)
    resolution = 120.0


class LocationFactory(ModelBaseFactory):
    class Meta:
        model = Location

    # latitude = factory.fuzzy.FuzzyFloat(-90.0, 90.0)
    # longitude = factory.fuzzy.FuzzyFloat(-180.0, 180.0)
    # This is the centre of london
    name = "My Fake location"
    timezone = "Europe/London"
    latitude = 51.0
    longitude = 0.12

    organization = "Fake organization"
    country = "England"
    locality = "Bristol"
    region = "Bristol"
    postalcode = "abc 123"
    street_address = "Big Building"


class EventDefinitionFactory(ModelBaseFactory):
    class Meta:
        model = EventDefinition

    enabled = True
    ref = "test_event_def"
    condition = "sum_250_power_sensor<5"
    actions = {"test_action": "test"}
    debounce_window = 600
    scheduled = False
    single_trigger = False
    product = factory.SubFactory(ProductFactory)


class DeviceEventDefinitionFactory(ModelBaseFactory):
    class Meta:
        model = EventDefinition

    enabled = True
    ref = "test_product_event_def"
    condition = "another_variable<another_value"
    actions = {"test_action": "also_a_test"}
    debounce_window = 600
    scheduled = False
    single_trigger = False
    device = factory.SubFactory(DeviceFactory)


class EventFactory(ModelBaseFactory):
    class Meta:
        model = Event

    device = factory.SubFactory(DeviceFactory)
    success = False
    definition = factory.SubFactory(EventDefinitionFactory)


class BilledOrganizationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BilledOrganization

    name = "Fake organization"


class BillGeneratorFactory(ModelBaseFactory):
    class Meta:
        model = BillGenerator

    enabled = True
    rate_per_device = 2
    currency = "GBP"
    period = "weekly"
    active_from_date = factory.LazyFunction(weeks_ago(12))
    organization = factory.SubFactory(BilledOrganizationFactory)


class BillFactory(ModelBaseFactory):
    class Meta:
        model = Bill

    paid = False
    period_start = factory.LazyFunction(weeks_ago(2))
    period_end = factory.LazyFunction(weeks_ago(1))
    generated_by = factory.SubFactory(BillGeneratorFactory)


class TimeSeriesDataFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TimeSeriesData

    sensor = factory.SubFactory(DeviceSensorFactory)
    value = factory.fuzzy.FuzzyFloat(0.0, 1.0)
    ts = factory.LazyFunction(datetime.datetime.utcnow)


class ProductFirmwareFactory(ModelBaseFactory):
    class Meta:
        model = ProductFirmware

    product = factory.SubFactory(ProductFactory)
    major = 3
    minor = 4
    patch = 5
    prerelease = "pre.2"
    build = "build.4"
    download_url = "http://test.com/download1"


class UpdateExecutionFactory(ModelBaseFactory):
    class Meta:
        model = UpdateExecution

    product_firmware = factory.SubFactory(ProductFirmwareFactory)
    strategy_class = "SimpleUpdate"
    enabled = True


class DeviceUpdateStatusFactory(ModelBaseFactory):
    class Meta:
        model = DeviceUpdateStatus

    time = factory.LazyFunction(datetime.datetime.utcnow)
    device = factory.SubFactory(DeviceFactory)
    error_message = "An error has occured"
    execution = factory.SubFactory(UpdateExecutionFactory)
    attempted = False
    success = False


class ActivitySubscriptionFactory(ModelBaseFactory):
    class Meta:
        model = ActivitySubscription

    user = factory.SubFactory(UserFactory)
    organization = factory.LazyFunction(OrganizationFactory)
    category = "business metric"
    min_severity = 10
    type = "email"


class OrganizationLogoFactory(ModelBaseFactory):
    class Meta:
        model = OrganizationLogo

    organization = factory.SubFactory(BilledOrganizationFactory)
    image = None

    @factory.post_generation
    def add_image(self, instance, step):
        if self.image:
            return
        logo = BytesIO()
        image = Image.new('RGBA', size=(50, 50), color=(155, 0, 0))
        image.save(logo, 'png')
        logo.name = 'red_logo.png'
        logo.seek(0)
        self.image = File(logo)


class DeviceEventDefWithActivityFactory(ModelBaseFactory):
    class Meta:
        model = EventDefinition

    enabled = True
    # Should email the site users
    ref = "test_ref"
    condition = "another_variable<another_value"
    actions = {
        "activity": {
            "verb": "reported",
            "description": "Message with aggregation: {ctx[sum_3600_power_sensor]}",
            "severity": 20,
            "category": "business metric",
            "notify": True
        }
    }
    debounce_window = 600
    scheduled = False
    single_trigger = False
    device = factory.SubFactory(DeviceFactory)


class DeviceStateFactory(ModelBaseFactory):
    class Meta:
        model = DeviceState

    version = 0
    device = factory.SubFactory(DeviceFactory)
