
class WorkerError(Exception):
    """Base class for worker errors - celery or message listener. No HTTP
    response because they aren't associated with a request."""


class WorkerFoundNoSuchDevice(WorkerError):
    """A worker was unable to find the requested device."""


class WorkerFoundNoSuchUser(WorkerError):
    """A worker was unable to find the requested user."""


class WorkerFoundNoSuchNotification(WorkerError):
    """A worker was unable to find the requested notification."""


class WorkerFoundNoSuchLocation(WorkerError):
    """A worker was unable to find a location for the user."""


class WorkerFoundNoSuchAction(WorkerError):
    """A worker was unable to find a location for the user."""


class WorkerNoConnectionError(WorkerError):
    """Running this action requires a watson conenction, which was not present"""


class WorkerReceivedInvalidEvent(WorkerError):
    """A worker received an event with invalid attributes or data."""


class TimeSeriesDataNotAllowed(WorkerError):
    """ A time series data allocation request was recieved for a
        document which doesn't allow it.
    """


class InvalidProductDefinition(WorkerError):
    """
    Raised when a worker is passed a device with an invalid product name
    """


class DeviceDoesNotHaveOwner(WorkerError):
    """
    Raised when a worker is passed a device with an invalid product name
    """


class SettingsKeyError(WorkerError):
    """
    Raised when a key that should be in settings wasn't found.
    """

class WorkerSMSError(WorkerError):
    """
    Raised when there is an error sending an SMS message.
    """


class BadMessageSchemaError(WorkerError):
    """A message with an invalid schema was sent from the device"""


class StateConflictError(WorkerError):
    """Tried to update device state but it was updated in the meantime"""
