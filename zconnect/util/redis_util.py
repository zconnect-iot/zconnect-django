import datetime
import logging
import time as ptime

from django.conf import settings
import redis

logger = logging.getLogger(__name__)


class RedisConnectionPoolSingleton:
    instance = None

    def __new__(cls, *args, **kwargs):
        if not cls.instance:
            redis_settings = settings.REDIS['connection']
            if 'username' in redis_settings:
                redis_settings.pop('username')
            # db=0 has been used here to suppress `KeyError` for `db`, must have worked in zc1
            # without, do not know if this will introduce any unwanted effects?
            cls.instance = redis.ConnectionPool(db=0, *args, **kwargs,
                                                **redis_settings)
        return cls.instance


def get_redis():
    pool = RedisConnectionPoolSingleton()
    return redis.StrictRedis(connection_pool=pool, decode_responses=True)


def check_redis():
    try:
        get_redis().ping()
    except redis.ConnectionError:
        return False
    return True


class RedisEventDefinitions:
    """
    A wrapper around event definition evaluation times stored in redis.
    """

    def __init__(self, strict_redis: redis.StrictRedis):
        self.redis = strict_redis
        self.redis_event_def_key = settings.REDIS['event_definition_evaluation_time_key']
        self.redis_event_def_state_key = settings.REDIS['event_definition_state_key']

    def get_eval_time(self, event_definition_id):
        last_time = self.get_redis_eval_time(event_definition_id)
        return float(last_time)

    def set_eval_time(self, event_definition_id, time=None):
        """
        Wrapper around setting redis event definition evaluation time.

        Args:
            event_definition_id: The event definition to set
            time (datetime.datetime): The time to set

        Returns:

        """

        if not time:
            ts = timestamp_now()
        else:
            ts = int(time.mktime(time.timetuple()))

        # For now, we'll also save this to redis.
        self.save_redis_eval_time(event_definition_id, timestamp=ts)

    def get_last_result(self, identifier):
        """ For an event def and device, get the last result to stop repeats

        Args:
            identifier (string): A unique identifier for the event definition
                and the device, used as the field in the Redis hash
        """
        state = self.redis.hget(self.redis_event_def_state_key, identifier)
        return bool(state and state == b"True")

    def set_last_result(self, identifier, result):
        """ For an event def and device, save the last result to stop repeats

        Args:
            identifier (string): A unique identifier for the event definition
                and the device, used as the field in the Redis hash
            result (bool): What did the condition of the event definition last
                evaluate to?
        """
        self.redis.hset(self.redis_event_def_state_key, identifier, result)

    def save_redis_eval_time(self, event_definition_id, timestamp=None):
        """
        Saves the last evaluation time (now) to redis for the specified event def
        Args:
            event_definition_id (EventDefinition): The event definition that was evaluated.
            timestamp (datetime): Unix timestamp that this event was evaluated.

        Returns:
            None

        """
        if not timestamp:
            timestamp = timestamp_now()

        self.redis.hset(self.redis_event_def_key, event_definition_id, timestamp)

    def get_redis_eval_time(self, event_definition_id):
        """
        It would be quite nice if we could do this with a cache, and avoid a little
        latency here. If we were to cache the hash on task start, we could do this,
        but we wouldn't be able to handle other tasks modifying redis during the task
        Args:
            event_definition (EventDefinition): The event definition that was evaluated.

        Returns:
            The timestamp
        """
        ts = self.redis.hget(self.redis_event_def_key, event_definition_id)
        if not ts:
            return first_evaluation_time()
        else:
            return float(ts.decode('utf-8'))


def first_evaluation_time():
    event_definition_evaluation_time_clock_skew_offset = \
        settings.REDIS['event_definition_evaluation_time_clock_skew_offset']
    return (datetime.datetime.utcnow() + datetime.timedelta(
                seconds=event_definition_evaluation_time_clock_skew_offset)
            ).timestamp()


def timestamp_now():
    """
    Return the current UTC unix timestamp.
    Returns:
        Unix timestamp as int.
    """
    dts = datetime.datetime.utcnow()
    epochtime = ptime.mktime(dts.timetuple())
    return int(epochtime)
