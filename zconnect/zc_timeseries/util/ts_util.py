import bisect
import datetime
import logging

from dateutil.relativedelta import relativedelta
from dateutil.rrule import DAILY, HOURLY, MONTHLY, WEEKLY, rrule

from zconnect.registry import get_preprocessor
from zconnect.tasks import send_triggered_events
from zconnect.util.redis_util import RedisEventDefinitions, get_redis
from zconnect.zc_timeseries.models import TimeSeriesData

logger = logging.getLogger(__name__)


def insert_timeseries_data(message, device):
    """
    Adds a timeseries datum to the database for all sensor_types in the message

    This will also call any preprocessors necessary

    """
    # Get the product and check for any preprocessors
    product = device.product

    preprocessors = product.preprocessors.all()

    for preprocessor in preprocessors:
        preprocessor = get_preprocessor(preprocessor.preprocessor_name)
        if preprocessor:
            preprocessor(message.body, device=device, ts_cls=TimeSeriesData)
        else:
            logger.warning("No preprocessor handler called %s on product %s",
                           preprocessor.preprocessor_name, product.name)

    for sensor in device.sensors.all():
        sensor_name = sensor.sensor_type.sensor_name
        if message.body.get(sensor_name) is not None:
            new_datum = TimeSeriesData(
                ts=message.timestamp,
                sensor=sensor,
                value=message.body[sensor_name]
            )
            new_datum.save()

    # Evaluate any definitions data with new datapoint
    context = device.get_context(context=message.body, time=message.timestamp)
    logger.debug("device context %s", context)
    redis_cache = RedisEventDefinitions(get_redis())

    triggered_events = device.evaluate_all_event_definitions(
        context, redis_cache, check_product=True
    )

    send_triggered_events(triggered_events, device, message.body)


def get_snapped_datetime(start, period):
    """Given a datetime, snap it to the specified window

    Args:
        start (datetime): timestamp
        period (str): one of VALID_AGGREGATION_PERIODS

    Returns:
        datetime: snapped datetime

    Example:

        >>> import datetime
        >>> from dateutil.parser import parse
        >>> three_am = parse('2018-07-02T03:41:00')
        >>> three_am
        datetime.datetime(2018, 7, 2, 3, 41)
        >>> snapped_6hour = get_snapped_datetime(three_am, '6hour')
        >>> snapped_6hour
        datetime.datetime(2018, 7, 2, 0, 0)
        >>> snapped_6hour.isoformat()
        '2018-07-02T00:00:00'

    Modified from: https://stackoverflow.com/a/32723408
    """

    if period == "1hour":
        # The same day, but withe verything else as 0
        floored = datetime.datetime(year=start.year, month=start.month, day=start.day)

        # List of hourly datetimes
        times = list(rrule(HOURLY, interval=1, dtstart=floored, count=25))
    elif period == "6hour":
        floored = datetime.datetime(year=start.year, month=start.month, day=start.day)
        # List of 6-hourly datetimes
        times = list(rrule(HOURLY, interval=6, dtstart=floored, count=5))
    elif period == "1day":
        floored = datetime.datetime(year=start.year, month=start.month, day=1)
        # List of daily datetimes
        # 32?
        times = list(rrule(DAILY, interval=1, dtstart=floored, count=32))
    elif period == "1week":
        floored = datetime.datetime(year=start.year, month=start.month, day=1)
        # List of daily datetimes
        times = list(rrule(WEEKLY, interval=1, dtstart=floored, count=5))
    elif period == "1month":
        floored = datetime.datetime(year=start.year, month=1, day=1)
        # List of monthly datetimes
        times = list(rrule(MONTHLY, interval=1, dtstart=floored, count=13))

    return times[bisect.bisect_left(times, start) - 1]


VALID_AGGREGATION_PERIODS = {
    "1hour": relativedelta(hours=1), # "One reading per hour",
    "6hour": relativedelta(hours=6), # "One reading per 6 hours",
    "1day": relativedelta(days=1), # "One reading per day",
    "1week": relativedelta(weeks=1), # "One reading per week",
    "1month": relativedelta(months=1), # "One reading per month",
}
