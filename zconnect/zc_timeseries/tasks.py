import datetime
import logging

from celery import shared_task

from zconnect import zsettings
from zconnect.util import exceptions
from zconnect.zc_timeseries.models import DeviceSensor, TimeSeriesData, TimeSeriesDataArchive
from zconnect.zc_timeseries.util.ts_util import VALID_AGGREGATION_PERIODS, get_snapped_datetime

logger = logging.getLogger(__name__)


@shared_task
def archive_old_ts_data():
    """Archive timeseries data

    Device sensors that need archiving:

    1. Should have timeseries data covering the whole period. Don't check to see
    if there is data missing in the middle, the aggregation takes care of that

    2. No ts data archive exists where the 'end' is after (now - one period).
    This works by 'snapping' the earliest timeseries data point that would be
    aggregated and checking that the period does not extend past the current
    date/time (otherwise we could be trying to archive data from the future)

    Assumes that the ARCHIVE_PRODUCT_AGGREGATIONS is like this:

    .. code-block:: python

        {
            # product iot_name:sensor name
            "a-product:temperature_sensor": {
                # List of aggregations. Supersedes aggregation_type on the
                # sensor_type model if present, otherwise use the one on the
                # model.
                "aggregations": [
                    "sum",
                    "max",
                ],
                # similar to billing periods in zc_billing.
                "period": "1week",
                # Whether to delete old data
                "delete_old_data": False,
            }
        }

    Because this will only archive one block at a time, it is advisable to set
    the schedule for running this task to be less than the period specified so
    that there isn't a 'lag' on archiving data for processing
    """

    logger.info("Running archive task for %s sensors", len(zsettings.ARCHIVE_PRODUCT_AGGREGATIONS))

    now = datetime.datetime.utcnow()

    for sensor_identifier, aggregation_settings in zsettings.ARCHIVE_PRODUCT_AGGREGATIONS.items():
        logger.debug("Running archive for %s", sensor_identifier)

        product_name, _, sensor_name = sensor_identifier.partition(":")

        period = aggregation_settings["period"]
        # It would be possible here to let people specify a custom relativedelta
        # as the 'period', but then figuring out what to 'snap' it to in the
        # function above becomes 100x more complicated. Better to just hardcode
        # a set.
        try:
            period_delta = VALID_AGGREGATION_PERIODS[period]
        except KeyError:
            raise exceptions.IncorrectAggregationError("'{}' is not a valid aggregation period".format(period))

        delete = aggregation_settings["delete_old_data"]

        # The earliest we could possible archive from
        period_start = now - period_delta

        logger.info("period_start = %s", period_start)

        # The DeviceSensor objects that use this sensor_type
        # This is the maximum number of device sensors that COULD be queried
        might_archive = DeviceSensor.objects.filter(
            sensor_type__product__iot_name=product_name,
            sensor_type__sensor_name=sensor_name,
        ).all()

        # Archives which exist for this period
        existing_archives = TimeSeriesDataArchive.objects.filter(
            end__gte=period_start,
        ).values_list("sensor", flat=True)

        # Filter DeviceSensor objects again to remove ones for which an archive
        # already exists for this period. Note that there might not be enough
        # timeseries data to actually perform an archive (eg, if we only have 1
        # data point so far). This is significantly harder to filter on, and
        # would require using a Window (which doesn't exist in sqlite anyway) so
        # we do it in a loop below. This is slow
        # FIXME
        needing_aggregation = might_archive.exclude(
            pk__in=existing_archives,
        )

        for ds in needing_aggregation:
            # NOTE
            # This will only collect one archive for each time the task is
            # called, so if a device needs more than one archive block
            # calculating it will be calculated the next time the task is run
            try:
                last_archive = ds.archive_data.latest()
            except TimeSeriesDataArchive.DoesNotExist:
                try:
                    # No archive data - check we have enough to archive
                    earliest = TimeSeriesData.objects.filter(
                        sensor=ds,
                    ).earliest()
                except TimeSeriesData.DoesNotExist:
                    logger.info("NO timeseries data for %s", ds)
                    continue
                else:
                    start = earliest.ts
                    # Snap the start to the last 'resolution' block
                    start = get_snapped_datetime(start, period)

                    end = start + period_delta

                    if end > now:
                        logger.info("Not enough data to archive for %s", ds)
                        if logger.isEnabledFor(logging.DEBUG):
                            latest = TimeSeriesData.objects.filter(
                                sensor=ds,
                            ).latest()
                            logger.debug("Earliest = %s, latest = %s (Would need up to %s)",
                                start, latest.ts, end)
                        continue
            else:
                # NOTE
                # This assumes it has been snapped correctly already. IF this
                # isn't a good assumption, get_snapped_datetime should be called
                # here as well
                start = last_archive.end
                end = start + period_delta

            for aggregation_type in aggregation_settings["aggregations"]:
                tsarchive = ds.archive_between(
                    start,
                    end,
                    aggregation_type=aggregation_type,
                    delete=delete,
                )

                tsarchive.save()
