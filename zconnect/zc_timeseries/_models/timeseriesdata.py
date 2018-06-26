from django.db import models

from zconnect.zc_timeseries.util.tsaggregations import AGGREGATION_CHOICES


class TimeSeriesData(models.Model):
    """Copied from django-timeseries, modified so we can use the primary key as
    a combination of the timestamp and the sensor it's associated with. Unlike
    in the examples in https://github.com/anthonyalmarza/django-timeseries, we
    are going to store one big TS table for sensor data (as well as an archive
    table for old aggregated data).

    This doesn't have add_datum because it doesn't really map to the SQL - just
    create a new datum with the correct devicesensor and it will raise a
    IntegrityError if it already exists

    Original docs:
        Abstract model that can be inherited from to facilitate building out
        your timeseries data framework.

        N.B. TimeSeries models should have a ForeignKey reference to an
        "owning" model and TIMESERIES_INTERVAL timedelta instance.

    Attributes:
        sensor (DeviceSensor): related sensor object on a specific device
        ts (datetime): Timestamp of this data
        value (float): sensor reading
    """

    ts = models.DateTimeField(db_index=True)
    sensor = models.ForeignKey("DeviceSensor", models.CASCADE, related_name="data", blank=False)
    value = models.FloatField()

    class Meta:
        ordering = ('-ts', )
        get_latest_by = 'ts'
        unique_together = ("ts", "sensor")

        indexes = [
            models.Index(fields=["sensor", "-ts"], name="ts_and_sensor_idx"),
        ]

    def __str__(self):
        return "{}: {}@{}".format(self.sensor.sensor_type.sensor_name, self.value, self.ts)


class TimeSeriesDataArchive(models.Model):
    """Archive which can be used to store lower resolution, aggregated data

    It may be useful to add a count of aggregated values in some situations.

    Attributes:
        aggregation_type (str): How this data was aggregated - eg 'min', 'max'
        start (datetime): start of aggregation period
        end (datetime): end of aggregation period
        sensor (DeviceSensor): Associated device sensor object
        value (float): result of aggregation
    """

    start = models.DateTimeField()
    end = models.DateTimeField()
    sensor = models.ForeignKey("DeviceSensor", models.CASCADE, related_name="archive_data")
    aggregation_type = models.CharField(max_length=20, choices=AGGREGATION_CHOICES)
    value = models.FloatField()

    class Meta:
        ordering = ('-end', )
        get_latest_by = 'end'
        unique_together = ("start", "end", "sensor", "aggregation_type")

        indexes = [
            models.Index(fields=["sensor", "-end"], name="end_and_sensor_idx"),
        ]
