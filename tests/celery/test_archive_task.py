import datetime
from freezegun import freeze_time
from math import sin
from unittest.mock import patch

from dateutil.relativedelta import relativedelta
from dateutil.parser import parse
import pytest

from zconnect.testutils.factories import DeviceSensorFactory
from zconnect.zc_timeseries.models import TimeSeriesData, TimeSeriesDataArchive
from zconnect.zc_timeseries.tasks import archive_old_ts_data
from zconnect.zc_timeseries.util.ts_util import get_snapped_datetime


@pytest.fixture(name="fake_data_resolution")
def default_resolution():
    """Note that this and the number of ts objects created below are fine tuned
    for these tests to create just over a week of data, and changing them might
    cause the tests to fail. See docstrings of tests for info"""
    return 20


@pytest.fixture(name="fakesensor")
def fix_fake_sensor_with_other_resolution(db, fakedevice, fake_data_resolution):
    """With custom resolution"""

    return DeviceSensorFactory(
        device=fakedevice,
        resolution=fake_data_resolution*60,
        sensor_type__sensor_name="Cool",
    )


def _generate_ts_data(fakesensor, fake_data_resolution):
    """Implementation of generating data

    needed for tests"""
    now = datetime.datetime.utcnow()

    tsd = TimeSeriesData.objects.bulk_create([
        TimeSeriesData(
            ts=now - relativedelta(minutes=fake_data_resolution*i),
            sensor=fakesensor,
            value=sin(i),
        ) for i in range(600)
    ])

    return tsd


@pytest.fixture(name="fake_ts_data_for_archiving")
def fix_fake_ts_data_more(fakedevice, fakesensor, fake_data_resolution):
    """Generate fake ts data

    returns all time series data objects"""
    return _generate_ts_data(fakesensor, fake_data_resolution)


def test_no_settings(fakesensor):
    """No settings - should do nothing"""

    with patch("zconnect.zc_timeseries.tasks.DeviceSensor.archive_between") as amock:
        archive_old_ts_data()

    assert not amock.called


@pytest.fixture(name="change_settings", autouse=True)
def fix_change_settings(settings, fakesensor):
    """Actually add settings to run archiving for fakesensor"""
    settings.ZCONNECT_SETTINGS.update(
        ARCHIVE_PRODUCT_AGGREGATIONS={
            "{}:{}".format(fakesensor.sensor_type.product.iot_name, fakesensor.sensor_type.sensor_name): {
                "aggregations": [
                    "sum",
                    "max",
                    "mean",
                ],
                "period": "1week",
                "delete_old_data": False,
            }
        }
    )


@pytest.mark.usefixtures("change_settings")
class TestArchiveSimple:

    def test_archive_no_data(self):
        """has settings, but no data to archive so should do nothing"""

        with patch("zconnect.zc_timeseries.tasks.DeviceSensor.archive_between") as amock:
            archive_old_ts_data()

        assert not amock.called

    def test_archive_not_long_enough_period(self, fake_ts_data):
        """Tried to aggregate for a week but data didn't go back further than a
        week"""

        assert TimeSeriesDataArchive.objects.all().count() == 0

        with patch("zconnect.zc_timeseries.tasks.DeviceSensor.archive_between") as amock:
            archive_old_ts_data()

        assert not amock.called

        assert TimeSeriesDataArchive.objects.all().count() == 0

    def test_archive_not_long_enough_period_long(self, fakesensor, fake_data_resolution, settings):
        """Same, but with 'longer' period"""
        for k, v in settings.ZCONNECT_SETTINGS["ARCHIVE_PRODUCT_AGGREGATIONS"].items():
            settings.ZCONNECT_SETTINGS["ARCHIVE_PRODUCT_AGGREGATIONS"][k]["period"] = "1month"

        # We generate ~a week of data, so need to freeze time to more than a
        # week after the start of the month so that snapping doesn't affect it
        with freeze_time("2018-06-26"):
            _generate_ts_data(fakesensor, fake_data_resolution)

            assert TimeSeriesDataArchive.objects.all().count() == 0

            with patch("zconnect.zc_timeseries.tasks.DeviceSensor.archive_between") as amock:
                archive_old_ts_data()

        assert not amock.called

        assert TimeSeriesDataArchive.objects.all().count() == 0

    def test_archive_long_enough_period(self, fake_ts_data_for_archiving):
        """the timeseries data straddles the week boundary so there will be
        'enough' in the PREVIOUS week to do an aggregation, but then when trying
        to do the next aggregation the period will straddle the current
        date/time so it will not do any archiving"""

        assert TimeSeriesDataArchive.objects.all().count() == 0

        archive_old_ts_data()

        # one for each aggregation
        assert TimeSeriesDataArchive.objects.all().count() == 3

        # It should run a second time without erroring and without archiving anything else
        with patch("zconnect.zc_timeseries.tasks.DeviceSensor.archive_between") as pmock:
            archive_old_ts_data()

        # Will not happen again
        assert not pmock.called
        assert TimeSeriesDataArchive.objects.all().count() == 3

    def test_archive_long_enough_period_long(self, fakesensor, fake_data_resolution, settings):
        """Same as above but for a month. Need to freeze time for same reason as
        above test"""
        for k, v in settings.ZCONNECT_SETTINGS["ARCHIVE_PRODUCT_AGGREGATIONS"].items():
            settings.ZCONNECT_SETTINGS["ARCHIVE_PRODUCT_AGGREGATIONS"][k]["period"] = "1month"

        with freeze_time("2018-06-03"):
            _generate_ts_data(fakesensor, fake_data_resolution)

            assert TimeSeriesDataArchive.objects.all().count() == 0

            archive_old_ts_data()

            assert TimeSeriesDataArchive.objects.all().count() == 3

            with patch("zconnect.zc_timeseries.tasks.DeviceSensor.archive_between") as pmock:
                archive_old_ts_data()

            # Will not happen again
            assert not pmock.called
            assert TimeSeriesDataArchive.objects.all().count() == 3


@pytest.mark.usefixtures("change_settings")
class TestRepeatArchive:
    """Running the archive should only generate 1 data point per agg type, you
    need to run it again to generate the next block"""

    @pytest.fixture(name="fake_data_resolution", params=[
        60,
        120,
        480,
    ])
    def default_resolution(self, request):
        return request.param

    def test_archive_first(self, fake_ts_data_for_archiving, fake_data_resolution):
        """Test that it can archive repeatedly"""

        assert TimeSeriesDataArchive.objects.all().count() == 0

        archive_old_ts_data()

        # one for each aggregation
        assert TimeSeriesDataArchive.objects.all().count() == 3

        # It should be able to run a few more times
        for i in range(0, fake_data_resolution, 60):
            archive_old_ts_data()

            j = i/60
            assert TimeSeriesDataArchive.objects.all().count() == (j+2)*3


@pytest.mark.parametrize("snap_to, expected", (
    ("1hour", "2018-07-21T08:00:00"),
    ("6hour", "2018-07-21T06:00:00"),
    ("1day", "2018-07-21T00:00:00"),
    ("1week", "2018-07-15T00:00:00"),
    ("1month", "2018-07-01T00:00:00"),
))
def test_snap_datetime(snap_to, expected):
    start = "2018-07-21T08:41:00"
    parsed = parse(start)

    assert get_snapped_datetime(parsed, snap_to).isoformat() == expected
