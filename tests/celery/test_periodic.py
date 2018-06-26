import contextlib
from datetime import datetime
from unittest.mock import Mock, patch

from freezegun import freeze_time
import pytest

from zconnect.tasks import (
    remove_old_periodic_data, trigger_scheduled_events, trigger_update_strategy)
from zconnect.testutils.factories import (
    DeviceSensorFactory, SensorTypeFactory, TimeSeriesDataFactory)
from zconnect.zc_timeseries.models import TimeSeriesData


def add_periodic_datums(data, device, product):
    """ Given a periodic document and a data point in the from

    ```
    {
        "temp": 23.0,
        "light": 1000,
        "ts": "2010-01-01T19:37:00Z"
    }
    ```

    Args:
    data (dict) - the data points to enter
    """
    data = data.copy()
    ts = data.pop('ts')
    for k,v in data.items():
        sensor_type = SensorTypeFactory(
            sensor_name=k,
            unit="",
            product=product
        )
        device_sensor = DeviceSensorFactory(
            device=device,
            resolution=120,
            sensor_type=sensor_type,
        )
        TimeSeriesDataFactory(
            ts=ts,
            value=v,
            sensor=device_sensor,
        )


@contextlib.contextmanager
def patch_sender():
    """ Patch the get_sender with the _return value_ set to a mock """
    fake_client = Mock()

    with patch("zconnect.tasks.get_sender", return_value=fake_client):
        yield fake_client


@pytest.mark.usefixtures("set_event_def")
class TestPeriodicTriggerDay:

    event_def = {
        "enabled": True,
        "ref": "temp:max",
        "condition": "time==7200&&day==2",
        "actions":{
            "alarm": False
        },
        "scheduled": True,
    }

    @pytest.mark.parametrize("time,expect_call", [
        ("2020-01-01T02:00:00Z", True),
        ("2020-01-01T02:00:01Z", True), # because of rounding
        ("2020-01-01T02:01:00Z", True), # True with new redis event system
        ("2020-01-01T01:00:00Z", False),
        ("2020-01-02T02:00:00Z", False),
        ("2020-07-01T02:00:00Z", True),
    ])
    @pytest.mark.usefixtures("first_event_evaluation_datetime_min")
    def test_periodic(self, time, expect_call, fakedevice, fakeproduct):
        """ test some combinations of periodic tiggers"""
        with patch_sender() as fake_client:
            with freeze_time(time):
                trigger_scheduled_events()
        assert fake_client.as_device.called == expect_call


@pytest.mark.usefixtures("set_event_def")
class TestPeriodicTriggerTemp:

    event_def = {
        "enabled": True,
        "ref": "temp:max",
        "condition": "time==7200&&temp>30",
        "actions":{
            "alarm": False
        },
        "scheduled": True,
    }

    @pytest.mark.parametrize("temp,expect_call", [
        (32, True),
        (29, False),
    ])
    @pytest.mark.usefixtures('first_event_evaluation_datetime_min')
    def test_periodic_conditions(self, temp, expect_call, fakedevice, fakeproduct):
        """ test some periodic conditions with additional context requirements """

        context = {
            "temp": temp,
            "ts": datetime(2020,1,1,2,0,0)
        }
        add_periodic_datums(context, fakedevice, fakeproduct)

        with patch_sender() as fake_client:
            with freeze_time("2020-01-01T02:00:00Z"):
                trigger_scheduled_events()

        assert fake_client.as_device.called == expect_call


@pytest.mark.usefixtures("set_event_def")
class TestPeriodicTriggerDay2:

    event_def = {
        "enabled": True,
        "ref": "temp:max",
        "condition": "time==7200&&day==2",
        "actions":{
            "alarm": False
        },
        "scheduled": True,
    }

    @pytest.mark.parametrize("time,expect_call", [
        ("2020-01-01T02:00:00Z", True),
        ("2020-01-01T02:00:01Z", True), # because of rounding
        ("2020-01-01T02:01:00Z", True), # True with redis events since it hasn't been previously evaluated.
        ("2020-01-01T01:00:00Z", False),
        ("2020-01-02T02:00:00Z", False),
        ("2020-07-01T02:00:00Z", True),
    ])
    @pytest.mark.usefixtures('first_event_evaluation_datetime_min')
    def test_periodic(self, time, expect_call):
        """ test some combinations of periodic tiggers"""
        with patch_sender() as fake_client:
            with freeze_time(time):
                trigger_scheduled_events()

        assert fake_client.as_device.called == expect_call

    @pytest.mark.usefixtures('first_event_evaluation_datetime_min')
    def test_redis_functionality(self):
        with patch_sender() as fake_client:
            with freeze_time("2020-01-01T02:00:00Z"):
                trigger_scheduled_events()

        assert fake_client.as_device.called == True

        # Now try again, redis should have saved the evaluation time, so it
        # shouldn't run it again.
        with patch_sender() as fake_client:
            with freeze_time("2020-01-01T02:05:00Z"):
                trigger_scheduled_events()

        # The condition has been evaluated since the time was greater than the
        # condition time, don't reevaluate.
        assert fake_client.as_device.called == False


@pytest.mark.usefixtures("set_event_def")
class TestDevicePeriodicTriggerDay1AndTime:

    event_def = {
        "enabled": True,
        "ref": "timeandday",
        "condition": "time==3600&&day==1",
        "actions":{
            "alarm": False
        },
        "scheduled": True,
    }

    @pytest.mark.usefixtures('first_event_evaluation_datetime_min')
    def test_redis_time_day_functionality(self, fakedevice, fakeproduct):
        """ Make sure that time and day triggers are working correctly."""
        # First test an event definition: time==3600&&day==1
        # If this is evaluated on day one before 3600 it should be false
        # If this is then evaluated on day one after 3600 it should be true
        # (even though the day is the same as the last evaluation)
        with patch_sender() as fake_client:
            with freeze_time("2019-12-31T00:30:00Z"):
                trigger_scheduled_events()

        assert fake_client.as_device.called == False

        with patch_sender() as fake_client:
            with freeze_time("2019-12-31T01:30:00Z"):
                trigger_scheduled_events()

        # Should be true since this was last evaluated before the time matched.
        assert fake_client.as_device.called == True


@pytest.mark.usefixtures("set_event_def")
class TestDeviceFieldEventDef:

    event_def = {
        "enabled": True,
        "ref": "devicefield",
        "condition": "device:online==False",
        "actions":{
            "alarm": False
        },
        "scheduled": True,
    }

    @pytest.mark.usefixtures('first_event_evaluation_datetime_min')
    def test_event_triggered_from_device_field(self, fakedevice, fakeproduct):
        """ Make sure that a condition which depends on a device field, in this
        case `online`, triggers event defs. """
        with patch_sender() as fake_client:
            trigger_scheduled_events()

        assert fake_client.as_device.called == True

    @pytest.mark.usefixtures('first_event_evaluation_datetime_min')
    def test_event_not_triggered_twice(self, fakedevice, fakeproduct):
        """ Make sure that a device field trigger only fires once """
        with patch_sender() as fake_client:
            trigger_scheduled_events()
            assert fake_client.as_device.call_count == 1
            trigger_scheduled_events()
            assert fake_client.as_device.call_count == 1



@pytest.mark.usefixtures("set_event_def")
class TestPeriodicTriggerDay1:

    event_def = {
        "enabled": True,
        "ref": "dayonly",
        "condition": "day==1",
        "actions": {
            "alarm": False
        },
        "scheduled": True,
    }

    @pytest.mark.usefixtures('first_event_evaluation_datetime_min')
    def test_redis_day_functionality(self, fakedevice, fakeproduct):
        """ Need to confirm exactly what this should do."""
        with patch_sender() as fake_client:
            with freeze_time("2019-12-30T23:30:00Z"):
                trigger_scheduled_events()

        # day == 0. So this should be false.
        assert fake_client.as_device.called == False

        # day == 1. So this should be True
        with patch_sender() as fake_client:
            with freeze_time("2019-12-31T00:30:00Z"):
                trigger_scheduled_events()

        assert fake_client.as_device.called == True

        with patch_sender() as fake_client:
            with freeze_time("2019-12-31T01:30:00Z"):
                trigger_scheduled_events()

        # Last time the condition was evaluated it was true so don't fire again
        assert fake_client.as_device.called == False


@pytest.mark.usefixtures("fakedevice")
class TestRemoveOldTimeSeriesData():

    def test_removes_old(self, fakedevice):
        with freeze_time("2015-01-01T00:00:00"):
            TimeSeriesDataFactory(ts=datetime.utcnow())
        before = TimeSeriesData.objects.count()
        remove_old_periodic_data()
        after = TimeSeriesData.objects.count()
        assert after == before - 1

    def test_leaves_new(self, fakedevice):
        TimeSeriesDataFactory(ts=datetime.utcnow())
        before = TimeSeriesData.objects.count()
        remove_old_periodic_data()
        after = TimeSeriesData.objects.count()
        assert after == before


@pytest.mark.usefixtures("fake_device_update_status")
class TestUpdateTask():
    def test_update_is_called(self):
        with patch('zconnect.tasks.apply_update_strategy') as patched:
            with patch_sender():
                trigger_update_strategy()

        assert patched.called
