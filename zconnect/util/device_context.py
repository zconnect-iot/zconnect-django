from datetime import datetime, timedelta
import logging

from django.db.models import Avg, Count, Max, Min, Sum

logger = logging.getLogger(__name__)

aggregation_map = {
    "sum": Sum,
    "avg": Avg,
    "min": Min,
    "max": Max,
    "count": Count
}

class AggregatedContext(dict):
    """ A modified dictionary which takes a device as an argument, as well as a context
    dict and also lazily calculates aggregation when using an appropriate aggregation key.

    Aggregation keys have the form '<aggreation_type>_<seconds>_<sensor_name>' where:
      - 'aggreation_type' must be one of 'sum', 'avg', 'min', 'max', 'count'
      - 'seconds' is the number of seconds into the past to which the aggregation is calculated
      - 'sensor_name' is the name of the sensor to calculate the aggregation for

    e.g.

    ..code-block:: python
        context = {
            "sensor_a": 12
        }
        context = AggregatedContext(device, context)

        # Getting values from passed in context
        print(context["sensor_a"])
        # prints "12"

        # Getting calculated values
        print(context["avg_3600_sensor_a"])
        # prints the average value of sensor_a over the past hour
        # e.g. "14"

        print(context["count_3600_sensor_a"])
        # prints the number of time series entries over the past hour

        # Getting values from the device
        print(context["name"])
        # prints "my cool device"

        # Getting values which don't exist raises a key error
        print(context["sensor_b"])
        # KeyError("'sensor_b' not a key in dictionary nor does it match the aggregation"
                " format of '<aggreation_type>_<seconds>_<sensor_name>'")

    When performing a lookup, the context will first attempt to look for the value
    in the internal dict (context+kwargs+device to __init__) and if not found will try
    to pass the key as an aggregation.

    Aggregation results are cached for the duration of the context life, so can be used
    in event_definitions as well as action handlers.

    The AggregatedContext is used for evaluating event definitions, as well as other
    templating contexts.
    """
    def __init__(self, device, context=None, agg_time=None, **kwargs):
        """
        Arguments:
            device (zconnect.models.Device) - The device used for the calculations
            context (dict) - Additional values to put on the context.
            agg_time (datetime.datetime) - The `now` time to use in aggregations, i.e. an aggregation
                            over 3600 seconds will run from `agg_time - 1 hour` through to `agg_time`.
                            This allows use of context for point in time calulations.
            kwargs (any) - additional kwargs will be part of the context dict.

        Returns: (AggregatedContext) - the enhanced dictionary
        """

        if not context:
            context = {}
        if not agg_time:
            agg_time = datetime.utcnow()

        self.__device = device

        # device fields have been added to context so event defs can depend
        super().__init__(device=device.__dict__, **context, agg_time=agg_time, **kwargs)

    def __getitem__(self, key):
        try:
            value = super(AggregatedContext, self).__getitem__(key)
        except KeyError:
            # Circular dep resolution
            from zconnect.zc_timeseries.models import TimeSeriesData
            # See if we can aggregate
            agg_type, seconds, sensor_name = self.parse_agg_key(key, self.__device)
            start = self["agg_time"] - timedelta(seconds=seconds)
            end = self["agg_time"]
            time_series_data = (
                TimeSeriesData.objects
                # Remove ordering to remove Django's secret fields which can result in
                # otherwise identical rows appearing to be distinct
                .order_by()
                .filter(
                    sensor__device=self.__device.id,
                    sensor__sensor_type__sensor_name=sensor_name,
                    ts__gte=start,
                    ts__lt=end,
                )
            )
            agg_func = aggregation_map[agg_type]
            value = time_series_data.aggregate(agg_func('value'))['value__{}'.format(agg_type)]

            # Cache the aggregation result
            self[key] = value

        return value

    def parse_agg_key(self, key, device):
        """ Function to parse the aggregation type, seconds and sensor name from aggregation key"""
        agg_types = list(aggregation_map.keys())
        sensor_names = [d.sensor_type.sensor_name.lower() for d in device.sensors.all()]
        try:
            split_arr = key.lower().split("_")
            agg_type = split_arr[0]
            seconds = split_arr[1]
            # Sensor name can contain underscores
            sensor_name = "_".join(split_arr[2:])
            if sensor_name == "":
                raise KeyError
        except (IndexError, KeyError):
            raise KeyError("'{}' not a key in dictionary nor does it match the aggregation"
                " format of '<aggreation_type>_<seconds>_<sensor_name>'".format(key))
        if agg_type not in agg_types:
            raise KeyError("'{}' not a key in dictionary nor is the aggregation_type '{}' one of"
                " the following: {}".format(key, agg_type, agg_types))
        try:
            seconds = int(seconds)
        except ValueError:
            raise KeyError("'{}' not a key in dictionary nor can the time period '{}' be parsed as"
                " an int".format(key, seconds))
        if sensor_name not in sensor_names:
            raise KeyError("'{}' not a key in dictionary nor is the sensor name '{}' one of the"
                " following: {}".format(key, sensor_name, sensor_names))
        return agg_type, seconds, sensor_name
