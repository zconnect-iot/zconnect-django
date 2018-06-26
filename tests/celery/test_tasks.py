import datetime

from django.apps import apps
from django.conf import settings
import pytest

from zconnect.tasks import check_device_online_status
from zconnect.testutils.factories import (
    DeviceSensorFactory, SensorTypeFactory, TimeSeriesDataFactory)


@pytest.mark.notavern
class TestCeleryTask:
    def test_device_recent_data(self, fakedevice, fake_ts_data):
        check_device_online_status.run(fakedevice)
        device = apps.get_model(settings.ZCONNECT_DEVICE_MODEL)
        assert device.objects.filter(id=fakedevice.id)[0].online is True

    def test_device_no_data(self, fakedevice):
        check_device_online_status.run(fakedevice)
        device = apps.get_model(settings.ZCONNECT_DEVICE_MODEL)
        assert device.objects.filter(id=fakedevice.id)[0].online is False

    def test_device_old_data(self, fakedevice, old_ts_data):
        check_device_online_status.run(fakedevice)
        device = apps.get_model(settings.ZCONNECT_DEVICE_MODEL)
        assert device.objects.filter(id=fakedevice.id)[0].online is False

    def test_evaluate_event_definitions(self,
                                        fake_device_event_def_activity,
                                        fake_redis_event_defs,
                                        fake_event_definition,
                                        simple_ts_data):
        (fakedevice, event_def) = fake_device_event_def_activity

        context = fakedevice.get_context()
        triggered_events = fakedevice.evaluate_all_event_definitions(context,
                                                                     fake_redis_event_defs,
                                                                     check_product=True
                                                                    )
        assert triggered_events == [fake_event_definition]


@pytest.mark.usefixtures("set_event_def")
class TestNoRepeats:

    event_def = {
        "enabled": True,
        "ref": "temp:max",
        "condition": "temp>50",
        "actions":{
            "alarm": False
        },
        "scheduled": True,
    }

    @pytest.mark.usefixtures('first_event_evaluation_datetime_min')
    def test_events_do_not_trigger_on_repeats(self, fakedevice, fakeproduct,
                                              fake_redis_event_defs):
        """ Test that a high temperature reading event fires exactly once """
        sensor_type = SensorTypeFactory(sensor_name="temp", unit="",
                                        product=fakeproduct)
        device_sensor = DeviceSensorFactory(device=fakedevice, resolution=120,
                                            sensor_type=sensor_type)
        # Test every combination (high-low, low-low, low-high, high-high)
        temps = [51, 49, 49, 51, 51]
        calls = [1, 0, 0, 1, 0]
        for i in range(5):
            # Change the timestamp to stop debouncing
            ts = datetime.datetime(2020,1,1,i,0,0)
            TimeSeriesDataFactory(ts=ts, value=temps[i], sensor=device_sensor)
            context = fakedevice.get_context()
            triggered = fakedevice.evaluate_all_event_definitions(
                context, fake_redis_event_defs, check_product=True
            )
            assert len(triggered) == calls[i]
