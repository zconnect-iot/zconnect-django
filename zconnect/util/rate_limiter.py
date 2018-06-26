#  -*- coding: utf-8 -*-
# Borrowed from https://github.com/EvoluxBR/python-redis-rate-limit
# Copied here due to the git version expecting
# redis to be on local host.

from distutils.version import StrictVersion  # pylint: disable=no-name-in-module,import-error
from hashlib import sha1

from redis.exceptions import NoScriptError

from .redis_util import get_redis

# Adapted from http://redis.io/commands/incr#pattern-rate-limiter-2
# Calls the EXPIRE command on the key on the first time it's
# used. This starts the window for the period. The returned value
# `current` will be tested in the python.
INCREMENT_SCRIPT = b"""
    local current
    current = tonumber(redis.call("incr", KEYS[1]))
    if current == 1 then
        redis.call("expire", KEYS[1], ARGV[1])
    end
    return current
"""
INCREMENT_SCRIPT_HASH = sha1(INCREMENT_SCRIPT).hexdigest()


class RedisVersionNotSupported(Exception):
    """
    Rate Limit depends on Redis’ commands EVALSHA and EVAL which are
    only available since the version 2.6.0 of the database.
    """
    pass


class TooManyRequests(Exception):
    """
    Occurs when the maximum number of requests is reached for a given resource
    of an specific user.
    """
    pass


class RateLimit:
    """
    This class offers an abstraction of a Rate Limit algorithm implemented on
    top of Redis >= 2.6.0.
    """
    def __init__(self, resource, client, max_requests, expire=None):
        """ Class initialization method checks if the Rate Limit algorithm is
        actually supported by the installed Redis version and sets some useful
        properties.

        If Rate Limit is not supported, it raises an Exception.

        Args:
            resource (str): resource identifier string (i.e. ‘user_pictures’)
            client (str): client identifier string (i.e. ‘192.168.0.10’)
            max_requests (int): ???
            expire (int): seconds to wait before resetting counters (i.e. ‘60’)

        Raises:
            RedisVersionNotSupported: If the version of redis we connected to
                is too old to support this implementation of rate limiting
        """
        self._redis = get_redis()

        if not self._is_rate_limit_supported():
            raise RedisVersionNotSupported()

        self._rate_limit_key = "rate_limit:{0}_{1}".format(resource, client)
        self._max_requests = max_requests
        self._expire = expire or 1

    def __enter__(self):
        self.increment_usage()

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def get_usage(self):
        """
        Returns actual resource usage by client. Note that it could be greater
        than the maximum number of requests set.

        Returns:
            int: current usage
        """
        return int(self._redis.get(self._rate_limit_key) or 0)

    def has_been_reached(self):
        """
        Checks if Rate Limit has been reached.

        Returns:
            bool: True if limit has been reached or False otherwise
        """
        return self.get_usage() >= self._max_requests

    def increment_usage(self):
        """
        Calls a LUA script that should increment the resource usage by client.
        If the resource limit overflows the maximum number of requests, this
        method raises an Exception.

        Returns:
            int: current usage

        Raises:
            TooManyRequests: If we are already over the max requests
        """
        try:
            current_usage = self._redis.evalsha(
                INCREMENT_SCRIPT_HASH, 1, self._rate_limit_key, self._expire)
        except NoScriptError:
            current_usage = self._redis.eval(
                INCREMENT_SCRIPT, 1, self._rate_limit_key, self._expire)

        if int(current_usage) > self._max_requests:
            raise TooManyRequests()

        return current_usage

    def _is_rate_limit_supported(self):
        """
        Checks if Rate Limit is supported which can basically be found by
        looking at Redis database version that should be 2.6.0 or greater.

        Returns:
            bool
        """
        redis_version = self._redis.info()['redis_version']
        is_supported = StrictVersion(redis_version) >= StrictVersion('2.6.0')
        return bool(is_supported)

    def _reset(self):
        """
        Deletes all keys that start with ‘rate_limit:’.
        """
        for rate_limit_key in self._redis.keys('rate_limit:*'):
            self._redis.delete(rate_limit_key)
