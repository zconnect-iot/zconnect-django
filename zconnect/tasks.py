from datetime import datetime
import logging

from celery import shared_task
from dateutil.relativedelta import relativedelta
from django.apps import apps
from django.conf import settings
from django.db.models import Q
from rest_auth.utils import import_callable

from zconnect.messages import Message, get_message_processor, get_sender
from zconnect.models import DeviceUpdateStatus, Product
from zconnect.util.redis_util import RedisEventDefinitions, get_redis
from zconnect.zc_timeseries.models import TimeSeriesData

logger = logging.getLogger(__name__)
Device = apps.get_model(settings.ZCONNECT_DEVICE_MODEL)


def send_triggered_events(triggered_events, device, context):

    for event_definition in triggered_events:
        logger.debug("Triggering event for device %s", str(device.id))

        try:
            context['ts'] = context['ts'].isoformat()
        except KeyError:
            pass # We don't mind if there's no timestamp

        event_data = {
            "event_id": "{}:{}".format(device.id, event_definition.id),
            "source": "server",
            "current": context,
        }
        logger.debug("Sending %s", event_data)

        # pylint: disable=broad-except
        try:
            get_sender().as_device(
                "event", event_data, device
            )
        except Exception:
            logger.exception("Sending event raised an error")


def evaluate_event_definitions(device, ts_data, redis_evaluation_times, event_definitions=None):
    """
    Evaluate event definitions on a device and trigger the appropriate action if
    they fire

    Args:
        device (Device): Device to evaluate definitions for
        ts_data (TimeSeriesData): Latest TS data for device
        redis_evaluation_times (RedisEventDefinitions): event definition evaluation times stored in redis
        event_definitions (None, optional): extra event definitions to evaluate
    """
    context = device.get_context()

    triggered_events = \
        device.evaluate_all_event_definitions(context,
                                              redis_evaluation_times,
                                              definitions=event_definitions,
                                              check_product=True,
                                             )

    # Basic, but serializable context
    basic_context = {k: v.value for k,v in ts_data.items()}

    send_triggered_events(triggered_events, device, basic_context)


@shared_task
def process_device_events_chunk(*devices):
    """ Evaluate event definitions for device
    """
    logger.debug("Checking events for devices %s", devices)

    redis_cache = RedisEventDefinitions(get_redis())

    ts_data = Device.latest_ts_data_optimised(devices)

    for device in devices:
        logger.debug("Checking events for device %s", device.id)

        evaluate_event_definitions(device, ts_data[device.id], redis_cache)


@shared_task
def check_device_online_status(*devices):
    """ Evaluate online status for devices
    """
    logger.debug("Checking device online status for devices %s", devices)

    for device in devices:
        logger.debug("Checking device online status for device %s", device.id)

        device.evaluate_online_status()


@shared_task
def trigger_scheduled_events():
    """Gets all scheduled tasks which should be triggered
    at the current time
    """

    logger.info("Running scheduled event definition evaluations")

    # TODO
    # optimise
    def chunk_devices(queryset, chunksize):
        """Chunk up the queryset into chunksize chunks"""
        logger.debug("%d devices", queryset.count())

        for i in range(0, queryset.count(), chunksize):
            yield queryset[i:i+chunksize]

    # Scheduled defs
    q_scheduled = Q(
        event_defs__scheduled=True,
    )

    scheduled_products = Product.objects.filter(q_scheduled)

    # All devices where the product has scheduled defs
    q_on_product = Q(
        product__in=scheduled_products,
    )

    # Shouldn't get any duplicates now because of the or
    query = Device.objects.filter(q_on_product | q_scheduled)

    # Magic number alert - this just means each 'job' will get 5 devices - note
    # this means that if there's 300 devices, this will create 60 chunks of size
    # 5. How these chunks are actually distributed to the tasks depends on the
    # number below!
    joined = chunk_devices(query, 5)

    # Split those chunks above among the workers. If there are 60 chunks as
    # above and 3 workers, this will split those 60 chunks into 12 'jobs', and
    # each worker will get *on average* 4 chunks, each with 5 of these 'jobs',
    # each with 5 devices. (4*5*5 = 100 = 1/3 of all devices)
    #
    # If there's 50 devices, this will result in 2 of the workers getting 25
    # devices. etc.
    return process_device_events_chunk.chunks(joined, 5).apply_async()


@shared_task
def remove_old_periodic_data():
    """Removes expired periodic_data from the db"""
    now = datetime.utcnow()
    # Just remove docs over 31 days old for now
    # TODO: this might need some really difficult
    # adjusting to make per product
    expired = now - relativedelta(days=31)

    TimeSeriesData.objects.filter(ts__lte=expired).delete()


def apply_update_strategy(execution, watson):
    """
    Given an UpdateExecution, apply it as per the update strategy

    Args:
        execution (UpdateExecution): The UpdateExecution document used to
            trigger this update
        watson (WatsonIoTSender): A watson sender instance
    """

    logger.debug("Attempting to apply update on %s", execution.id)

    # Get the update strategy class and call the apply method.
    strategy = import_callable(execution.strategy_class)

    try:
        strategy.apply(execution, watson)
    except Exception as e: # pylint: disable=broad-except
        logger.exception("Exception thrown while running apply update for "
                         "Update Execution: %s Exception: %s", execution.id, e)


@shared_task
def trigger_update_strategy():
    """
    Iterates through all incomplete and enabled update executions and applies
    them.
    """

    logger.debug("Checking for updates to apply.")

    filters = {
        'execution__enabled': True,
        'success': False,
    }
    update_statuses = DeviceUpdateStatus.objects.filter(**filters)

    watson = get_sender()

    if not update_statuses:
        logger.debug("No updates")

    for update_status in update_statuses:
        # TODO
        # farm out to workers
        apply_update_strategy(update_status.execution, watson)


@shared_task
def send_mqtt_message(topic, payload):
    sender = get_sender()

    sender.interface.client.publish(topic, payload)


@shared_task
def process_message(message):
    logger.debug("Processing a message %r", message)
    # Accepts a message or a dict with the right fields
    if not isinstance(message, Message):
        message = Message.from_dict(message)

    logger.info("Celery processing of Message %r", message)
    mp = get_message_processor()
    mp.process(message)
