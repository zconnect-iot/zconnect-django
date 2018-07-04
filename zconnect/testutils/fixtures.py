import datetime
from io import BytesIO
from math import sin
from unittest.mock import patch

from PIL import Image
from dateutil.relativedelta import relativedelta
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import Permission
from django.core.files import File
import factory
import pytest
from rest_framework.test import APIClient

from zconnect._messages.message import Message
from zconnect.testutils.util import weeks_ago
from zconnect.zc_timeseries.models import TimeSeriesData, TimeSeriesDataArchive

from .client import BBTestClient, TavernClient
from .factories import (
    ActivitySubscriptionFactory, BilledOrganizationFactory, BillFactory, BillGeneratorFactory,
    DeviceEventDefinitionFactory, DeviceEventDefWithActivityFactory, DeviceFactory,
    DeviceSensorFactory, DeviceUpdateStatusFactory, EventDefinitionFactory, EventFactory,
    GroupFactory, LocationFactory, OrganizationLogoFactory, ProductFactory, ProductFirmwareFactory,
    UpdateExecutionFactory, UserFactory)

# pylint: disable=attribute-defined-outside-init


@pytest.fixture(scope="function", name="testclient")
def fix_testclient(request, client, db):
    """Get a wrapper around the django test client

    request = pytest fixture
    client = pytest-django fixture
    db = pytest-django fixture

    Returns:
        django.test.Client: The test app object
    """

    try:
        inst = request.instance
        route = inst.route
    except AttributeError:
        pytest.fail("testclient can only be used on a class with a 'route' attribute")

    if request.config.getoption("--tavernize-tests"):
        client = TavernClient(request, route)
    else:
        client = BBTestClient(APIClient(), route)

    yield client


@pytest.fixture(name="fredbloggs")
def fix_fredbloggs(db):
    """Returns a user who isn't joe seed. Just for testing inter-user interactions.

    Same password
    """
    password = "test_password"
    fred = UserFactory(
        first_name="fred",
        last_name="bloggs",
        username="fredbloggs@zoetrope.io",
        email="fredbloggs@zoetrope.io",
        password=make_password(password)
    )
    return fred


@pytest.fixture(name="fredbloggs_login")
def fix_fredbloggs_login(fredbloggs, testclient):
    """Make all requests using this fixture be logged in as an fred bloggs"""
    testclient.login(fredbloggs.username, "test_password")
    return fredbloggs


@pytest.fixture(name="fake_group")
def fix_fake_group(db):
    """Create a fake group for testing"""
    return GroupFactory()


@pytest.fixture(name="fake_org")
def fix_fake_org(db):
    return BilledOrganizationFactory()

@pytest.fixture(name="fake_org_2")
def fix_fake_orgs(db):
    return BilledOrganizationFactory()


@pytest.fixture(name="joeseed")
def fix_joeseed(db, fake_group, fake_org):
    """Returns a normal user, password hardcoded

    This will be put in the 'fake_group' which should implicitly give it access
    to 'fakedevice' via django guardian permissions
    """
    password = "test_password"
    joe = UserFactory(
        password=make_password(password),
        # FIXME
        # groups list on device?
    )
    joe.groups.add(fake_group)
    joe.add_org(fake_org)
    # joe.orgs.add(fake_org)
    joe.save()
    return joe


@pytest.fixture(name="joeseed_login")
def fix_joeseed_login(joeseed, testclient):
    """Make all requests using this fixture be logged in as an joeseed"""
    testclient.login(joeseed.username, "test_password")
    return joeseed


@pytest.fixture(name="adminuser")
def fix_adminuser(db):
    password = "admin_password"
    admin = UserFactory(
        email="admin@zoetrope.io",
        username="admin@zoetrope.io",
        password=make_password(password),
        is_superuser=True,
        is_staff=True,
        first_name="bart",
        last_name="simpson",
    )
    return admin


@pytest.fixture(name="admin_login")
def fix_admin_login(adminuser, testclient):
    """Make all requests using this fixture be logged in as an admin"""
    testclient.login(adminuser.username, "admin_password")

@pytest.fixture(name="normal_user")
def fix_normaluser(db):
    password = "normal_password"
    norm = UserFactory(
        email="norm@zoetrope.io",
        username="norm",
        password=make_password(password),
        is_superuser=False,
        is_staff=False,
    )
    return norm


@pytest.fixture(name="normal_user_login")
def fix_normal_user_login(normal_user, testclient):
    """Make all requests using this fixture be logged in as a normal user"""
    testclient.login(normal_user.username, "normal_password")

@pytest.fixture(name="timeseries_user")
def fix_timeseries_user(db):
    password = "timeseries_password"
    norm = UserFactory(
        email="ts@zoetrope.io",
        username="ts",
        password=make_password(password),
        is_superuser=False,
        is_staff=False,
    )
    perm = Permission.objects.get(codename='can_create_timeseries_http')
    norm.user_permissions.add(perm)
    return norm

@pytest.fixture(name="timeseries_user_login")
def fix_timeseries_user_login(timeseries_user, testclient):
    """
    Make all requests using this fixture be logged in as a normal user with
    the timeseries permission
    """
    testclient.login(timeseries_user.username, "timeseries_password")

@pytest.fixture(name="fakelocation")
def fix_fakelocation(db):
    """Get fake device"""
    return LocationFactory()


@pytest.fixture(name="fakeproduct")
def fix_fakeproduct(db):
    """Get fake product"""
    return ProductFactory()


@pytest.fixture(name="fake_product_firmware")
def fix_fake_product_firmware(db):
    """Get fake product firmware"""
    return ProductFirmwareFactory()


@pytest.fixture(name="fake_update_execution")
def fix_fake_update_execution(db):
    """Get fake update execution"""
    return UpdateExecutionFactory()


@pytest.fixture(name="fake_device_update_status")
def fix_fake_device_update_status(db, fakedevice, fake_update_execution):
    """Get fake device update status"""
    return DeviceUpdateStatusFactory(device=fakedevice, execution=fake_update_execution)


@pytest.fixture(name="fakedevice")
def fix_fakedevice(db, fake_org, fakeproduct):
    """Get fake device"""
    device = DeviceFactory(product=fakeproduct)
    device.orgs.add(fake_org)
    device.save()
    return device


@pytest.fixture(name="fakedevices")
def fix_fakedevices(db, fake_org):
    """Get fake devices"""
    devices = [
        DeviceFactory(
            name="test device {}".format(i),
        ) for i in range(10)
    ]
    for d in devices:
        d.orgs.add(fake_org)
        d.save()
    return devices


@pytest.fixture(name="fakesensor")
def fix_fake_sensor(db, fakedevice):
    """Get fake sensor on fakedevice"""
    return DeviceSensorFactory(device=fakedevice)


@pytest.fixture(name="fake_ts_data")
def fix_fake_ts_data(fakesensor, db):
    """Generate fake ts data

    returns all time series data objects"""
    now = datetime.datetime.utcnow()

    tsd = TimeSeriesData.objects.bulk_create([
        TimeSeriesData(
            ts=now - relativedelta(minutes=2*i),
            sensor=fakesensor,
            value=sin(i),
        ) for i in range(1200)
    ])

    return tsd


@pytest.fixture(name="fake_ts_archive_data")
def fix_fake_ts_archive_data(fakesensor, db):
    now = datetime.datetime.utcnow()

    tsd = TimeSeriesDataArchive.objects.bulk_create([
        TimeSeriesDataArchive(
            start=now - relativedelta(weeks=i+1),
            end=now - relativedelta(weeks=i),
            aggregation_type=at,
            sensor=fakesensor,
            value=sin(i),
        ) for i in range(8) for at in ["mean", "sum"]
    ])

    return tsd


@pytest.fixture(name="simple_ts_data")
def fix_simple_ts_data(fakesensor, db):
    """Generate simple ts data

    returns all time series data objects"""
    now = datetime.datetime.utcnow()

    tsd = TimeSeriesData.objects.bulk_create([
        TimeSeriesData(
            ts=now - relativedelta(minutes=2*i),
            sensor=fakesensor,
            value=i,
        ) for i in range(4)
    ])

    return tsd


@pytest.fixture(name="old_ts_data")
def fix_old_ts_data(fakesensor, db):
    """Generate old fake ts data

    returns all time series data objects"""
    ts = datetime.datetime.utcnow() - datetime.timedelta(minutes=15)

    tsd = TimeSeriesData.objects.bulk_create([
        TimeSeriesData(
            ts=ts - relativedelta(minutes=2*i),
            sensor=fakesensor,
            value=sin(i),
        ) for i in range(1200)
    ])

    return tsd


@pytest.fixture(name="fake_event_definition")
def fix_event_definition(db, fakeproduct):
    """Get fake event definition"""
    return EventDefinitionFactory(product=fakeproduct)


@pytest.fixture(name="fake_device_event_definition")
def fix_fake_device_event_definition(db, fakedevice):
    return DeviceEventDefinitionFactory(device=fakedevice)

@pytest.fixture(name="fake_event")
def fix_fake_event(db, fakedevice, fake_event_definition):
    """Get fake event on fakedevice"""
    return EventFactory(device=fakedevice, definition=fake_event_definition)


@pytest.fixture(name="fake_activity_subscription")
def fixactivity_subscription(db):
    """Generate fake activity subscription"""
    activity_subscription = ActivitySubscriptionFactory()
    return activity_subscription


@pytest.fixture(name="fake_bill_generator")
def fix_fake_bill_generator(db):
    return BillGeneratorFactory()


@pytest.fixture(name="fake_bill")
def fix_fake_bill(db, fake_bill_generator, fakedevice):
    bill = BillFactory(generated_by=fake_bill_generator)
    bill.devices.add(fakedevice)
    return bill


@pytest.fixture(name="fake_bill_old")
def fix_fake_bill_old(db, fake_bill_generator, fakedevice):
    bill = BillFactory(generated_by=fake_bill_generator,
                       period_start = factory.LazyFunction(weeks_ago(3)),
                       period_end = factory.LazyFunction(weeks_ago(2)))
    bill.devices.add(fakedevice)
    return bill


@pytest.fixture
def first_event_evaluation_datetime_min():
    def min_eval_time():
        # 1970-01-01T01:00
        return datetime.datetime(1970,1,1,1).timestamp()

    with patch('zconnect.util.redis_util.first_evaluation_time', min_eval_time):
        yield


@pytest.fixture(name="set_event_def", params=[True, False])
def fix_set_event_def(request, fakedevice, fakeproduct):
    """ param = set it on the device or not

    event definitions should be triggered on either """

    inst = request.instance

    if inst is None:
        pytest.fail("Need an instance")

    event_def = inst.event_def

    if request.param:
        DeviceEventDefinitionFactory(device=fakedevice, **event_def)
    else:
        EventDefinitionFactory(product=fakeproduct, **event_def)

@pytest.fixture(name="fake_watson_ts_event")
def fix_fake_watson_ts_event(fakedevice, fakesensor, fakeproduct):
    # Fake sensor will be power_sensor
    print("Adding sensor: {}".format(fakesensor))
    fakesensor.product = fakedevice.product
    fakesensor.save()

    print("sensor: {}".format(fakedevice.sensors.all()))

    fake_data = {
        "power_sensor": 123.0
    }
    message = Message(
        category='periodic',
        body=fake_data,
        device=fakedevice
    )

    return (fakedevice, message)

@pytest.fixture(name="red_logo")
def fix_red_logo():
    logo = BytesIO()
    image = Image.new('RGBA', size=(50, 50), color=(155, 0, 0))
    image.save(logo, 'png')
    logo.name = 'red_logo.png'
    logo.seek(0)
    return File(logo)

@pytest.fixture(name="green_logo")
def fix_green_logo():
    logo = BytesIO()
    image = Image.new('RGBA', size=(50, 50), color=(0, 155, 0))
    image.save(logo, 'png')
    logo.name = 'green_logo.png'
    logo.seek(0)
    return File(logo)

@pytest.fixture(name="fake_org_logo")
def fix_fake_org_logo():
    return OrganizationLogoFactory()


@pytest.fixture(name="fake_device_event_def_activity")
def fix_fake_device_event_def_with_activity(db, joeseed, fake_org, fakedevice):
    """
    Provides a device with an event definition containing email actions.
    Also includes a site on the device and adds Joe Seed to that site.
    """
    ev = DeviceEventDefWithActivityFactory(device=fakedevice)
    return (fakedevice, ev)


class FakeRedisEventDefs():
    def __init__(self, eval_time):
        self.eval_time = float(eval_time)
        self.cache = {}

    def get_eval_time(self, event_def_id):
        return (datetime.datetime.utcnow() - datetime.timedelta(seconds=self.eval_time)).timestamp()

    def set_eval_time(self, event_def_id):
        return

    def get_last_result(self, event_def_id):
        try:
            return self.cache[event_def_id]
        except KeyError:
            return False

    def set_last_result(self, event_def_id, result):
        self.cache[event_def_id] = result


@pytest.fixture(name="fake_redis_event_defs")
def fix_fake_redis_event_defs():
    return FakeRedisEventDefs(172800) #2 days
