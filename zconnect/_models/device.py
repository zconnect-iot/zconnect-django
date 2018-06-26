import copy
import datetime
import logging
from typing import Dict, List

from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.db import IntegrityError, models, transaction
from django.db.models.functions import window
from django.utils.translation import ugettext_lazy as _
from organizations.models import Organization

from zconnect.messages import Message, verify_message_schema
from zconnect.util import exceptions
from zconnect.util.device_context import AggregatedContext
from zconnect.util.event_condition_parser import Condition

from .base import ModelBase
from .event import Event
from .mixins import EventDefinitionMixin

logger = logging.getLogger(__name__)


class AbstractDevice(EventDefinitionMixin, ModelBase):
    """ Abstract device class

    This has to be abstract to allow the user to choose their own device model
    or extend it. If we just inherit from a non-abstract device model then we
    enter all kinds of horrible stuff with undocumented django functions and
    circular dependencies in migrations

    A device can be 'owned' by one or more groups, not that this doesn't inherit
    from PermissionsMixin like a user does - it just uses the groups so that
    we have a list of groups for using with django-guardian

    Attributes:
        event_defs (list): Any event definitions that are device specific (in
            addition to any that might be on the product)
        last_seen (DateTime): Time of last communication from this device
        location (Location): Location of device (eg, 'Main office')
        product (Product): What kind of product this device is
        settings (DeviceSettings): Device specific settings
        state (DeviceState): State of this device
        user_meta (UserMeta): Information that a user can set on this device
        watson_details (WatsonDetails): Watson specific details for device
        orgs (list(Organization)): groups that 'own' this device.
        online (Boolean): True if this device is online
    """

    product = models.ForeignKey("zconnect.Product", models.PROTECT, blank=False)
    last_seen = models.DateTimeField(null=True, blank=True)
    # location = models.ForeignKey("Location", blank=True, null=True)

    name = models.CharField(max_length=50)

    online = models.BooleanField(default=False)
    fw_version = models.CharField(max_length=50, blank=True)

    orgs = models.ManyToManyField(
        Organization,
        verbose_name=_('organizations'),
        blank=True,
        help_text=_("Organizations that 'own' this device"),
        related_name="devices",
        related_query_name="device",
    )

    class Meta:
        abstract = True

    def __str__(self):
        # pylint: disable=missing-format-attribute
        return '{self.name} ({self.product}, id: {self.id})'.format(self=self)

    def get_iot_id(self):
        """Gets the watson iot device id. This is always a string of the
        objectID in the database.

        Returns:
            str: currently objectid of device
        """
        return str(self.id)

    def clear_settings(self):
        """Cleans device state, settings, and event definition on the device
        """
        self.online = False
        self.fw_version = None

        # Delete event defs from database
        for ev_def in self.event_defs.all():
            ev_def.delete()

    def factory_reset(self):
        """Completely wipe all settings of device - settings, state, location - then save
        """
        # pylint: disable=attribute-defined-outside-init
        self.location = None
        # FIXME
        # Need to call some kind of groups.clear thing here
        self.groups = None
        self.clear_settings()
        self.save()

    def evaluate_all_event_definitions(self,
                                       context: Dict,
                                       redis_event_state,
                                       string_matchers: List = None,
                                       direct_comparison: str = None,
                                       definitions: List = None,
                                       check_product: bool = False) -> List:
        """
        Evaluates all event definitions on the device against the passed in
        context and returns a list of triggered event definitions.

        Args:
            context (Dict): The context to evaluate event definitions against
            redis_event_state (RedisEventDefinitions): An object with getter &
                setter to get & set evaluation times and last results in Redis.
            string_matchers (List, optional): Any strings that must be included
                in the event definition. Can be useful to improve performance
            direct_comparison (str, optional): A direct comparison to an event
                definition string. Can be useful to improve performance
            definitions (List, optional): A list of event definitions if they
                should not be pulled from the device.
            check_product (bool, optional): Whether to check the device's
                product for any Event definitions

        Returns:
            list: A list of event definitions which should be triggered.
        """

        if not definitions:
            definitions = self.event_defs.all()

        if check_product:
            # If the product has any event definitions, add them to those we
            # are evaluating
            if getattr(self.product, 'event_defs', None):
                # The `|` operator merges querysets
                definitions = definitions | self.product.event_defs.all()

        logger.debug(
            "Evaluate all event definitions on device: %s with context: %s",
            self.id, context)

        triggered_events = []

        # Add any device and product settings.
        context.setdefault('settings', {}).update({
            'device': getattr(self, 'settings', {}),
            'product': getattr(self.product, 'settings', {}),
        })

        for event_definition in definitions:
            logger.debug("Evaluating %s", event_definition)
            if not event_definition.enabled:
                continue

            if direct_comparison and direct_comparison == event_definition.condition:
                logger.info("Condition matched exactly. %s",
                            event_definition.condition)
                # Exact match with no other conditions, skip conditions etc.
                if self.debounce_allow_triggered_event(event_definition):
                    triggered_events.append(event_definition)
                continue

            if string_matchers:
                if not all(x in event_definition.condition for x in
                           string_matchers):
                    # If we don't have all the string matches, skip this one.
                    continue

            # create a key that is unique to the device and event definition
            debounce_key = "{}:{}".format(self.id, event_definition.id)

            last_eval_time = redis_event_state.get_eval_time(debounce_key)

            redis_event_state.set_eval_time(debounce_key)

            # Evaluate any keywords.
            condition = Condition(event_definition.condition)
            result = condition.evaluate(context, last_eval_time=last_eval_time)
            previous = redis_event_state.get_last_result(debounce_key)
            if result:
                logger.debug("Condition %s evaluated to True",
                             event_definition.condition)
                if self.debounce_allow_triggered_event(event_definition):
                    if not previous:
                        triggered_events.append(event_definition)
            redis_event_state.set_last_result(debounce_key, result)

        return triggered_events

    def debounce_allow_triggered_event(self, event_definition):
        """Check the debounce and maybe add it to the list.

        Args:
            event_definition (EventDefinition) The event we're looking to debounce
                debounce

        Returns:
            bool: True if the event is not being suppressed by debounce rules.
                    False if the event should not be propogated.
        """

        # Currently debounce is disabled if an exact time match is used
        debounce = 'time==' not in event_definition.condition

        # Get the previous time this event was triggered to
        # determine the debounce window. Get any events of this
        # type which have triggered within the window.
        if debounce:
            debounced_time = datetime.datetime.utcnow() - \
                             relativedelta(seconds=event_definition.debounce_window)
            count = Event.objects.filter(
                device=self,
                definition=event_definition.id,
                created_at__gte=debounced_time,
            ).count()
            add_event = (count == 0)
            logger.debug("Debounce lookup returned %s for count %s since %s \
                                (event_definition: %s)",
                            add_event, count, debounced_time.isoformat(),
                            event_definition.id
            )
        else:
            add_event = True

        if add_event:
            return True
        else:
            logger.info("Suppressing event (%s) due to debounce rules.",
                        event_definition.condition)
            return False

    @classmethod
    def delete_user_hook(cls, user):
        """ Removes the user and the location from the devices which
        the user being deleted owns

        Args:
            user (User): user document that was just deleted
        """

        number_updated = cls.objects(owner=user).update(owner=None, location=None,
                                                        org_permissions=[], event_defs=[],
                                                        settings={},
                                                        online=False, fw_version=None)

        logger.info("Deletion of user: %s caused %s devices to be removed from that user",
                     user.id, number_updated)

    def get_latest_ts_data(self):
        """For each sensor on the given device, get the latest reading

        Todo:
            This makes a query for each sensor on the device because we can use
            .latest to make this easy. Would probably need to actually write
            some SQL to do this in one query

            This should also be a 'proxy model' in zconnect.zc_timeseries or
            however it's done in django where you can just add a method to an
            existing model without changing the DB

        Returns:
            dict: mapping of sensor name: latest TimeSeriesData reading
        """

        from zconnect.zc_timeseries.models import DeviceSensor

        sensors = DeviceSensor.objects.filter(
            device=self,
        )

        readings = {}

        logger.debug("Sensors: %s", sensors)

        readings = AbstractDevice.latest_ts_data_optimised([self])

        return readings[self.id]

    @classmethod
    def latest_ts_data_optimised(cls, devices):
        """Get latest ts data for multiple devices

        Args:
            devices (list): list of devices to get data for

        Returns:
            dict: mapping of sensor name: latest TimeSeriesData reading

        Todo:
            inner join on the sensors/devices will take nulls into account
            without raising a doesnotexist error
        """
        from zconnect.zc_timeseries.models import DeviceSensor, TimeSeriesData

        if "postgres" not in settings.DATABASES["default"]["ENGINE"]:
            logger.warning("Using slower method of getting ts data when not using postgresql")

            readings = {}

            for device in devices:
                device_readings = {}

                for sensor in device.sensors.all():
                    data = sensor.get_latest_ts_data()
                    logger.debug("Latest for %s: %s", sensor.sensor_type.sensor_name, data)
                    device_readings[sensor.sensor_type.sensor_name] = data

                readings[device.id] = device_readings

            return readings

        # Define a window that partitions the data by the sensor and annotates
        # each row with the 'first' value, based on the timestamp (eg, the most
        # recent)
        w_last = models.Window(
            expression=window.FirstValue("id"),
            partition_by=models.F("sensor"),
            order_by=models.F("ts").desc(),
        )

        # All sensors for all devices
        sensors = DeviceSensor.objects.filter(device__in=devices)

        # Use the window to get a set of the ids corresponding to the most
        # recent timestamps for each sensor
        ids = (
            TimeSeriesData.objects
                # Filter by sensor
                .filter(sensor__in=sensors)
                # Annotate rows with the most recent timestamp for that sensor
                .annotate(last_reading_id=w_last)
                # Needed for distinct() to work
                .order_by()
                # Only get unique last_reading_id. Don't care which one as we
                # extract this field anyway
                .distinct("last_reading_id")

                # Return only this annotated value
                .values_list("last_reading_id", flat=True)
        )

        # Then just filter on the ids
        raw_data = (
            TimeSeriesData.objects
                .filter(pk__in=ids)

                # Prefetch here or else it generates a new query for each access
                # to .sensor or .sensor.sensor_type
                # This is 2 extra queries, but it's ALWAYS 2, not 2 for each device
                .prefetch_related("sensor__sensor_type")
        )

        # Then 'annotate' the names into a dictionary
        data = {device.id: {} for device in devices}
        for d in raw_data:
            device_id = d.sensor.device_id
            sensor_name = d.sensor.sensor_type.sensor_name
            data[device_id][sensor_name] = d

        logger.debug(data)
        return data

    def get_context(self, context=False, time=False):
        """ Return a context object for use in event definition evaluation/templating
        or other places where device context is needed.

        currently, either both context and time need to be provided or just context,
        since support for looking up the time series data at a point in time has not
        been created.

        Args:
            context (dict) optional - If provided, this is the context dictionary
                    (normally in a time series handler).
            time (datetime) optional - If provided the context should be as of
                        this time. That will mean it will return the most recent time
                        series values before the time provided.

        Todo:
            Implement `get_latest_ts_data` for a point in time.
        """
        if time and not context:
            raise Exception("Not implemented for point-in-time yet")

        if not context:
            ts_data = self.get_latest_ts_data()
            context = {k: v.value for k,v in ts_data.items()}
            context["ts"] =  time if time else datetime.datetime.utcnow()

        return AggregatedContext(self, context, agg_time=time)

    def optimised_data_fetch(self, data_start, data_end=None, resolution=None):
        """Get data for device for a certain range and possible average it

        Args:
            data_start (datetime): Beginning of data block
            data_end (datetime): End of data block. now if not passed.
            resolution (int): aggregation factor - this has to be a common
                multiple of all the resolutions of all sensor poling requencies
                on the device (eg, if resolutions are 2, 4, 6 then resolution
                here needs to be 24)

        Todo:
            This can be optimised like above. This should be much easier though;
            just move the single queries off the DeviceSensor model and into
            this function.

        Returns:
            dict(list): mapping of sensor name: data for given time block
        """

        from zconnect.zc_timeseries.models import DeviceSensor

        if not resolution:
            # FIXME
            # Find the LCM of all sensor readings? Or just return raw data?
            resolution = 120.0
        else:
            resolution = int(resolution)

        if not data_end:
            data_end = datetime.datetime.utcnow()

        sensors = DeviceSensor.objects.filter(
            device=self,
        )

        readings = {}

        for sensor in sensors:
            data = sensor.optimised_data_fetch(data_start, data_end, resolution)
            readings[sensor.sensor_type.sensor_name] = data

        return readings

    def evaluate_online_status(self):
        """
        Evaluates time series data device and updates `online` status, classed as offline if no
        data recieved for over `threshold_mins`
        """
        try:
            threshold_mins = settings.REDIS['online_status_threshold_mins']
        except (AttributeError, KeyError):
            # Default to 10 minutes if not in settings file
            threshold_mins = 10
        online = False
        now = datetime.datetime.utcnow()

        ts_data = self.get_latest_ts_data()
        for sensor in ts_data:
            ts = ts_data[sensor].ts
            time_diff = now - ts
            (mins, _) = divmod(time_diff.total_seconds(), 60)
            if mins < threshold_mins:
                online = True
                break
        if self.online is not online:
            self.online = online
            self.save()
        return

    def get_allowed_activity_categories(self):
        return ["business metric", "maintenance", "system"]

    @property
    def notify_organizations(self):
        """ This property can be subclassed in projects to define which organizations
        are to be used for notifying actions on this organization.
        """
        return self.orgs

    def get_latest_state(self):
        """Get latest DeviceState

        Note that this returns both the reported and the desired state which may
        be different - call latest_state.delta to get the differences
        """
        from .states import DeviceState
        try:
            return DeviceState.objects.filter(device=self).latest()
        except DeviceState.DoesNotExist:
            logger.debug("Device has no state yet, starting at version 0", exc_info=True)
            initial_state = DeviceState(
                device=self,
                version=0,
            )
            initial_state.save()
            return initial_state

    def _attempt_device_state_update(self, changing, new_state, error_on_other_change=False):
        """Actually attempt a state update

        This will try to save the new state 3 times then error out to avoid an
        infinite loop if there's 2 parts of the system which are responding to
        one another by updating the state repeatedly.

        See documentation for update_reported_state and update_desired_state for
        arguments
        """
        if changing == "desired":
            other = "reported"
        elif changing == "reported":
            other = "desired"
        else:
            raise Exception("Invalid value for 'changing' passed")

        latest_state = self.get_latest_state()
        version = latest_state.version + 1

        from .states import DeviceState

        for i in range(3): # pylint: disable=unused-variable
            try:
                with transaction.atomic():
                    new_latest_state = DeviceState(
                        device=self,
                        version=version,
                        **{
                            changing: new_state,
                            other: getattr(latest_state, other),
                        }
                    )

                    logger.debug("Updating %s state for %s with %s (version %s)", changing, self.pk, new_state, version)

                    new_latest_state.save()
            except IntegrityError as e:
                logger.warning("Device state changed when trying to save")
                latest_state = self.get_latest_state()

                if getattr(latest_state, other) != getattr(new_latest_state, other):
                    if error_on_other_change:
                        logger.error("State changed while trying to update it")
                        raise exceptions.StateConflictError from e
                    else:
                        logger.debug("%s state changed - ignoring", other)

                if getattr(latest_state, changing) == getattr(new_latest_state, changing):
                    version = latest_state.version + 1
                else:
                    logger.error("%s state was updated somewhere else while trying to update it here", changing)
                    raise exceptions.StateConflictError from e
            else:
                logger.debug("Change state successfully")
                break
        else:
            # fallthrough
            logger.error("Could not set new %s state after 3 attempts", changing)
            raise exceptions.StateConflictError

        return new_latest_state

    def update_reported_state(self, new_state, verify=False):
        """Given a new reported state from a device, create a new DeviceState
        object in the database

        If the reported state changes between us reading the last state and us
        trying to save a new state, there is another race condition somewhere
        which is a fairly fatal error which we can't do anything about. We don't
        care if the desired state changes though, as that should be handled
        somewhere else or on the device

        Args:
            new_state (dict): The 'reported' state from the device. This should
                be the RAW state, ie no 'state' or 'reported' key
            verify (bool): If True, verification will be done to make sure it
                matches the expected Product state layout. If not, assume it has
                already been validated.

        Raises:
            BadMessageSchemaError: If verify is True and message validation
                fails

        Returns:
            DeviceState: new state document
        """

        if verify:
            wrapped = {
                "body": {
                    "state": {
                        "reported": new_state
                    },
                },
                "device": self.pk,
                "category": "reported_state",
                "timestamp": datetime.datetime.utcnow(),
            }
            message = Message.from_dict(wrapped)
            verify_message_schema(message)

        return self._attempt_device_state_update("reported", new_state)

    def update_reported_state_from_message(self, message):
        """Utility to update device state directly from a Message"""
        return self.update_reported_state(new_state=message.body, verify=True)

    def update_desired_state(self, new_state, verify=True,
            error_on_reported_change=False):
        """Given a new desired state for a device, create a new DeviceState
        object in the database

        If the state update succeeds, it will send a message to the device to
        tell it that it should try and change to the desired state

        If the state is updated but it raises an integrity error, another
        thread/process might have changed the state. In this case, if it is just
        the device reporting that it's state has changed and
        error_on_reported_change is True, raise an error. This will always be
        raised if the desired state changes.

        If the reported state changes but error_on_reported_change is False,
        just set the new state document to contain that reported state and
        return to the user. note that this does hide information from the
        developer, but the reported state change should be handled in another
        process anyway.

        Todo:
            What if it can save to the DB, but the MQTT message can't be sent?
            If we send the message before saving the state there is a race
            condition, but if we save the state before sending we need to buffer
            the 'change state' message somehow so it can be sent

        Args:
            new_state (dict): The new 'desired' state for the device. This should
                be the RAW state, ie no 'state' or 'reported' key
            verify (bool): If True, verification will be done to make sure it
                matches the expected Product state layout. If not, assume it has
                already been validated.

        Raises:
            BadMessageSchemaError: If verify is True and message validation
                fails
            StateConflictError: If the state is changed elsewhere while trying
                to save a new state (according to rules described above)

        Returns:
            DeviceState: new state document
        """

        wrapped = {
            "body": {
                "state": {
                    "desired": new_state
                },
            },
            "device": self.pk,
            "category": "desired_state",
            "timestamp": datetime.datetime.utcnow(),
        }

        if verify:
            v_dict = copy.deepcopy(wrapped)
            v_dict["body"]["state"]["reported"] = v_dict["body"]["state"].pop("desired")
            v_msg = Message.from_dict(v_dict)
            verify_message_schema(v_msg)

        new_latest_state = self._attempt_device_state_update("desired", new_state, error_on_reported_change)

        message = Message.from_dict(wrapped)
        message.send_to_device()

        return new_latest_state


class Device(AbstractDevice):
    class Meta:
        ordering = ["product"]
        swappable = "ZCONNECT_DEVICE_MODEL"
        # NOTE
        # Seems like this needs to be set on all things you want to use
        # django-guardian with - 'view' is not a default permission for some
        # reason (I suppose to allow anonymous viewing)
        default_permissions = ["view", "change", "add", "delete"]
