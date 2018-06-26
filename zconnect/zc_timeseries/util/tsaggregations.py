import datetime
import logging
from math import nan
from statistics import median

from django.db import models
from django.db.models.aggregates import Aggregate, Avg, Max, Min, Sum
from django.db.models.functions import window
import numpy as np

from zconnect.util.db_util import format_query_sql

logger = logging.getLogger(__name__)


def aggregate_numpy(raw, aggregation_type, aggregation_factor, expected_samples,
        data_start, data_end, sensor):
    """Aggregate given TS data based on given factor and aggregation function

    Args:
        raw (list(tuple)): A list of tuples of (value, timestamp) for each
            TimeSeriesData value to be archived
        aggregation_type (str): name of aggregation (eg 'max', 'min')
        aggregation_factor (int): factor to aggregate data by. for example, if
            there are 40 values and the aggregation_factor is 4, every 4 values
            will be aggregated and 10 values will be returned.
        expected_samples (int): Expected number of final samples
        data_start (datetime): first timestamp of data to aggregate
        data_end (datetime): last timestamp of data to aggregate
        sensor (zc_timeseries.Sensor): Sensor object that the TimeSeriesData is
            related to

    Returns:
        list(TimeSeriesData): New (unsaved) TS data objects aggregated given
            input parameters
    """
    aggregations = {
        "sum": np.sum,
        "mean": np.mean,
        "median": np.median,
        "min": np.amin,
        "max": np.amax,
    }

    agg_func = aggregations[aggregation_type]

    as_np = np.asarray(raw)

    ts_vals = as_np[:,0]
    raw_timestamps = as_np[:,1]

    # If the number doesn't match there is either missing data or too much
    # data - in this case we have to bin the data before using it

    ts_reduce_factor = int(sensor.resolution*aggregation_factor)
    # Range of timestamps from the start to the end time, spaced evenly by
    # the amount that the data will be aggregated by
    bins = np.arange(data_start.timestamp(), data_end.timestamp(), ts_reduce_factor)

    # Convert all datetimes to timestamps
    as_timestamp = np.vectorize(lambda x: x.timestamp())
    converted = as_timestamp(raw_timestamps)

    # Bin output
    binned = np.digitize(converted, bins)

    # Now we have a list of indexes that matches each input value to which
    # bin it should be in in the output. This might be more or less than the
    # expected_samples.

    aggregated = np.zeros((int(expected_samples/aggregation_factor),))

    # TODO
    # Could be possible to do this without a loop
    for bn in range(aggregated.size):
        samples = ts_vals[binned==bn+1]

        if not len(samples): # pylint: disable=len-as-condition
            aggregated[bn] = nan
        else:
            aggregated[bn] = agg_func(samples)

    # Now construct the actual objects
    from zconnect.zc_timeseries.models import TimeSeriesData

    def yield_dates():
        """Yield datetime objects which increase at the same rate as the
        aggregated data points"""
        current = data_start
        while True:
            yield current
            # Add after yielding the first value because the timestamp is
            # for the next hour
            current += datetime.timedelta(seconds=sensor.resolution*aggregation_factor)

    def construct_objects():
        for value, ts in zip(aggregated, yield_dates()):
            yield TimeSeriesData(ts=ts, value=value, sensor=sensor)

    data = list(construct_objects())

    return data


def aggregate_sql(raw, aggregation_type, aggregation_factor, periods):
    """Use SQL windows to calculate the average

    This should be quicker

    Note:
        this doesn't work in sqlite

    Todo:
        This needs work - implementing a custom Expression or Func in django and
        using it instead of annotating the annotated QS, which doesn't work
    """
    aggregations = {
        "sum": Sum,
        "mean": Avg,
        "median": median,
        "min": Min,
        "max": Max,
    }

    # pylint: disable=unreachable

    aggregation_function = aggregations[aggregation_type]

    raise NotImplementedError("This is not yet finished")

    if isinstance(aggregation_function, type) and issubclass(aggregation_function, Aggregate):
        # A tile window expression that will split the queryset into an
        # even number of chunks
        tile_window = models.Window(
            expression=window.Ntile(num_buckets=aggregation_factor),
            order_by=models.F("ts").desc(),
        )

        # A window that will calculate the average of a window
        # partitioned by the 'ntile' attribute
        aggregate_window = models.Window(
            expression = aggregation_function("value"),
            partition_by=[models.F("ntile")],
        )

        # This creates a new queryset with all the original values in
        # it, but also an extra annotated value called 'ntile' which
        # corresponds to which tile it's been partitioned into
        tiled = raw.annotate(ntile=tile_window)

        # Then we do ANOTHER window function, which partitions based on
        # this tile number and does the actual annotation.
        data = tiled.annotate(agg=aggregate_window)

        logger.info(format_query_sql(data))
    else:
        # TODO
        # just call the numpy one
        pass


aggregation_implementations = {
    "numpy": aggregate_numpy,
    "sql": aggregate_sql,
}


GRAPH_CHOICES = [
    ("ts_bar", "Bar graph"),
    ("ts_graph", "Line graph"),
]


AGGREGATION_CHOICES = [
    ("sum", "Sum values over the aggregation period"),
    ("mean", "Mean of values over the aggregation period"),
    ("median", "Median of values over the aggregation period"),
    ("min", "Minimum value over the aggregation period"),
    ("max", "Maximum value over the aggregation period"),
]
