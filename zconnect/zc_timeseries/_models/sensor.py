import logging
from math import fmod

import django
from django.conf import settings
from django.db import models

from zconnect.models import ModelBase
from zconnect.util import exceptions
from zconnect.zc_timeseries.util.tsaggregations import (
    AGGREGATION_CHOICES, GRAPH_CHOICES, aggregation_implementations)

logger = logging.getLogger(__name__)


# Sentinel that just indicates that the data should be aggregated into one
# point. This prevents 2 queries being done
AGGREGATE_TO_ONE_VALUE = object()


class SensorType(ModelBase):
    """A type of sensor

    Attributes:
        aggregation_type (str): Default aggregation to perform for this sensor
            type - eg 'avg', 'sum'
        descriptive_name (str): Longer description of sensor
        graph_type (str): What kind of graph this should be shown as in the app
            (bar or graph)
        product (Product): which product this sensor is associated with
        sensor_name (str): name of sensor
        unit (str): Unit of measurement (eg, "Watts")
    """

    # The canonical name for this sensor
    sensor_name = models.CharField(max_length=50, blank=True)

    # A human readable sensor name, could be displayed under graphs etc.
    descriptive_name = models.CharField(max_length=50, blank=True)
    unit = models.CharField(max_length=30)
    graph_type = models.CharField(max_length=20, choices=GRAPH_CHOICES, default="ts_graph")
    aggregation_type = models.CharField(max_length=20, choices=AGGREGATION_CHOICES, default="sum")
    # products can't be deleted until all devices are deleted as well. Once we
    # can delete it, all sensor types are a bit pointless to keep, so delete
    # them instead.
    product = models.ForeignKey("zconnect.Product", models.CASCADE, related_name="sensors", blank=False)

    class Meta:
        unique_together = ["sensor_name", "product"]


class DeviceSensor(ModelBase):
    """A sensor associated with a device

    Attributes:
        device (Device): associated device
        resolution (float): how often this is sampled, in seconds
        sensor_type (SensorType): type of sensor
    """

    resolution = models.FloatField(default=120.0)
    # If device goes, just delete this. device should never be deleted really
    # though
    device = models.ForeignKey(settings.ZCONNECT_DEVICE_MODEL, models.CASCADE, related_name="sensors", blank=False)
    # Can't leave the sensor type null
    sensor_type = models.ForeignKey(SensorType, models.PROTECT, blank=False)

    class Meta:
        # NOTE
        # This seems to make sense but it would break in the case that a device
        # has multiple of the same sensor.
        unique_together = ("device", "sensor_type")

    def get_latest_ts_data(self):
        """Get latest ts data on this sensor for this device

        The latest_ts_data_optimised on AbstractDevice should be used instead of
        directly calling this
        """

        from .timeseriesdata import TimeSeriesData

        try:
            data = TimeSeriesData.objects.filter(
                sensor=self,
            ).latest("ts")
        except TimeSeriesData.DoesNotExist:
            # If the device hasn't made any timeseries data yet.
            return {}

        return data

    def _get_aggregated_data(self, data_start, data_end, resolution, aggregation_type):
        """Implementation of aggregating data. See other functions for meanings
        of arguments.

        Raises:
            TimeSeriesData.DoesNotExist: If there is no data in the given period
        """
        from .timeseriesdata import TimeSeriesData

        # Multiple of resolution
        # We extract just the values_list here because doing it in a
        # separate statement results in django querying the database
        # twice...
        raw = TimeSeriesData.objects.filter(
            ts__gte=data_start,
            ts__lt=data_end,
            sensor=self,
        ).values_list("value", "ts")

        if not raw:
            # This should raise above but for some reason it doesn't when using
            # values_list
            raise TimeSeriesData.DoesNotExist

        # How many samples we would expect if there was no missing data
        expected_samples = (data_end - data_start).total_seconds()/self.resolution

        if resolution is AGGREGATE_TO_ONE_VALUE:
            aggregation_factor = expected_samples
        else:
            # Already checked that this divides nicely
            # NOTE
            # should aggregation_factor ALWAYS be expected_samples?
            aggregation_factor = int(resolution//self.resolution)

        logger.debug("%s objects to aggregate", len(raw))

        aggregation_engine = aggregation_implementations[settings.ZCONNECT_TS_AGGREGATION_ENGINE]

        logger.debug("Aggregating '%s' with %s, factor %s",
            aggregation_type, settings.ZCONNECT_TS_AGGREGATION_ENGINE,
            aggregation_factor)

        data = aggregation_engine(
            raw,
            aggregation_type,
            aggregation_factor,
            expected_samples,
            data_start,
            data_end,
            self,
        )

        return data

    def optimised_data_fetch(self, data_start, data_end, resolution):
        """Get data from given time block and possibly average it

        See Device.optimised_data_fetch for args

        This function assumes all the input data is already validated.
        """

        if resolution < self.resolution or fmod(resolution, self.resolution):
            raise django.db.DataError("Resolution should be a multiple of {} (was {})".format(
                self.resolution, resolution))

        from .timeseriesdata import TimeSeriesData

        # XXX
        # equals for floats? If resolution is not a whole number this won't work
        if resolution == self.resolution:
            # No aggregation, just get the data
            # It's already sorted by time in the database
            data = TimeSeriesData.objects.filter(
                sensor=self,
                ts__gte=data_start,
                ts__lt=data_end,
            )
        else:
            data = self._get_aggregated_data(
                data_start,
                data_end,
                resolution,
                self.sensor_type.aggregation_type,
            )

        return data

    def archive_between(self, data_start, data_end, *, aggregation_type=None, delete=False):
        """Create a ts archive between the start and data_end dates

        This does it like ``[data_start, data_end)`` - including start, not end

        If delete is True, also delete the old ts data.

        Args:
            data_start (datetime): start of archive
            data_end (datetime): end of archives

        Keyword args:
            delete (bool, optional): delete old ts data if True
            aggregation_type (str, optional): If this is passed then it will use
                that aggregation type rather than the 'default' on the sensor
                type. This has to be one of
                zc_timeseries.util.tsaggregations.AGGREGATION_CHOICES or it will
                raise an error. Note that some of these choices may be
                meaningless for certain data types (eg, sum of temperatures over
                a month is a bit useless)

        Returns:
            TimeSeriesDataArchive: archive of data between data_start and data_end

        Raises:
            TimeSeriesData.DoesNotExist: If there is no data between data_start and
                data_end
        """

        from .timeseriesdata import TimeSeriesData, TimeSeriesDataArchive

        if not aggregation_type:
            aggregation_type = self.sensor_type.aggregation_type
        elif aggregation_type not in (i[0] for i in AGGREGATION_CHOICES):
            raise exceptions.IncorrectAggregationError("'{}' is not a valid aggregation".format(aggregation_type))

        data = self._get_aggregated_data(
            data_start,
            data_end,
            AGGREGATE_TO_ONE_VALUE,
            aggregation_type,
        )

        logger.debug("to archive: %s", data)

        archived = TimeSeriesDataArchive(
            start=data_start,
            end=data_end,
            value=data[0].value,
            sensor=self,
            aggregation_type=aggregation_type,
        )
        archived.save()

        logger.debug("archived %s to %s with %s: %s", archived.start, archived.end, self.sensor_type.aggregation_type, archived.value)

        if delete:
            TimeSeriesData.objects.filter(
                sensor=self,
                ts__gte=data_start,
                ts__lt=data_end,
            ).delete()

        return archived
