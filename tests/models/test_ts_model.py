import datetime

import django
import pytest

from zconnect.testutils.factories import DeviceSensorFactory
from zconnect.util import exceptions
from zconnect.zc_timeseries.models import TimeSeriesData
from zconnect.zc_timeseries.util.tsaggregations import AGGREGATION_CHOICES


class TestTSModel:

    def test_unique_same_sensor(self, fakesensor):
        """Same ts with same sensor raises an error"""
        now = datetime.datetime.utcnow()

        TimeSeriesData.objects.create(
            ts=now,
            sensor=fakesensor,
            value=1.0,
        )

        with pytest.raises(django.db.utils.IntegrityError):
            TimeSeriesData.objects.create(
                ts=now,
                sensor=fakesensor,
                value=1.0,
            )

    def test_unique_different_sensor(self, fakesensor):
        """Same ts but different sensors from different devices should be
        fine"""
        now = datetime.datetime.utcnow()

        TimeSeriesData.objects.create(
            ts=now,
            sensor=fakesensor,
            value=1.0,
        )

        extra_sensor = DeviceSensorFactory()

        TimeSeriesData.objects.create(
            ts=now,
            sensor=extra_sensor,
            value=1.0,
        )


class TestArchive:

    def test_archive_data_no_data(self, fakesensor):
        """No data raises an exception"""
        now = datetime.datetime.utcnow()

        with pytest.raises(TimeSeriesData.DoesNotExist):
            fakesensor.archive_between(
                now - datetime.timedelta(hours=1),
                now,
            )

    def test_archive_with_data(self, fake_ts_data, fakesensor):
        now = datetime.datetime.utcnow()

        archived = fakesensor.archive_between(
            now - datetime.timedelta(hours=1),
            now,
        )

        assert archived.end == now

    def test_archive_with_data_deletes(self, fake_ts_data, fakesensor):
        """Getting data and passing 'delete' should remove old data

        this results in an exception being raised if it is called again"""
        now = datetime.datetime.utcnow()

        archived = fakesensor.archive_between(
            now - datetime.timedelta(hours=1),
            now,
            delete=True,
        )

        assert archived.end == now

        with pytest.raises(TimeSeriesData.DoesNotExist):
            archived = fakesensor.archive_between(
                now - datetime.timedelta(hours=1),
                now,
            )

    def test_archive_wrong_aggregation_type(self, fakesensor):
        """Not a valid aggregation type raises an error"""
        now = datetime.datetime.utcnow()

        with pytest.raises(exceptions.IncorrectAggregationError):
            fakesensor.archive_between(
                now - datetime.timedelta(hours=1),
                now,
                aggregation_type="magic",
            )

    def test_archive_wrong_aggregation_type_no_delete(self, fake_ts_data, fakesensor):
        """Passing delete=true with an invalid aggregation shouldn't delete the data"""
        now = datetime.datetime.utcnow()

        with pytest.raises(exceptions.IncorrectAggregationError):
            archived = fakesensor.archive_between(
                now - datetime.timedelta(hours=1),
                now,
                aggregation_type="magic",
                delete=True,
            )

        # Calling with default sensor aggregation type should work
        archived = fakesensor.archive_between(
            now - datetime.timedelta(hours=1),
            now,
            delete=True,
        )

        assert archived.end == now

        # And it should now be deleted correctly
        with pytest.raises(TimeSeriesData.DoesNotExist):
            archived = fakesensor.archive_between(
                now - datetime.timedelta(hours=1),
                now,
            )

    @pytest.mark.parametrize("aggregation_type", [
        i[0] for i in AGGREGATION_CHOICES
    ])
    def test_all_aggregation_types(self, fake_ts_data, fakesensor, aggregation_type):
        """Currently all aggregations should work for all ts data"""
        now = datetime.datetime.utcnow()

        archived = fakesensor.archive_between(
            now - datetime.timedelta(hours=1),
            now,
            aggregation_type=aggregation_type,
        )

        assert archived.end == now
