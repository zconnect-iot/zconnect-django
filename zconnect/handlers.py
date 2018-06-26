import datetime
import logging

from django.conf import settings

from zconnect.activity_stream import device_activity
from zconnect.messages import Message
from zconnect.models import Event, EventDefinition
from zconnect.registry import decorators, get_action_handlers
from zconnect.util import comms, exceptions
from zconnect.zc_timeseries.util.ts_util import insert_timeseries_data

logger = logging.getLogger(__name__)


@decorators.message_handler(name='periodic')
def time_series_message_handler(message, listener):
    device = message.device
    insert_timeseries_data(message, device)


@decorators.message_handler(name="event")
def event_message_handler(message, listener):
    """ This is how event definitions have their actions triggered """
    _, event_def_id = message.body["event_id"].split(":")

    try:
        event_def = EventDefinition.objects.get(id=int(event_def_id))
    except EventDefinition.DoesNotExist:
        logger.exception("Event definition %s does not exist! device: %s",
                            event_def_id, message.device.id)
        return

    event_instance = Event(
        device = message.device,
        definition = event_def,
        success = True,
    )

    # Attempt to run the event action handlers
    if event_def.actions:

        for key, args in event_def.actions.items():
            handlers = get_action_handlers(key)

            if not handlers:
                logger.error("Event definition %s has action key for %s, "\
                                "but there were no handlers", event_def_id, key)
                event_instance.success = False
                continue

            for handler in handlers:
                # pylint: disable=broad-except
                try:
                    handler(
                        message,
                        listener=listener,
                        action_args=args,
                        event_def=event_def,
                        # TODO: we may want to expose this in future
                        #event=event_instance,
                    )
                except Exception:
                    logger.exception("event action \"%s\" failed!", key)
                    event_instance.success = False

    event_instance.save()
    logger.info("Event definition %s completed on device %s. success: %s. event.id: %s",
        event_def_id, message.device.id, event_instance.success, event_instance.id)


@decorators.message_handler(name='status')
def process(message, listener):
    """Process a status update.

    Params:
        status (ibmiotf.Status) - the status object.

    Args:
        message (Message): zconnect Message object that triggered this handler
        listener (Listener): zconnect message Listener that called this handler
    """
    logger.debug('Connection message status %s', message)
    if message.body == 'Connect':
        online = True
    elif message.body == 'Disconnect':
        online = False
    elif message.body == 'FailedConnect':
        return
    else:
        logger.warning("Unknown status action %s", message.body)
        return

    try:
        device = message.device
        device.online = online
        device.last_seen = datetime.datetime.utcnow()
        device.save()
        logger.info(
            'Connection message success (device: %s) (action: %s)',
            message.device.id, message.body
        )

        # Note: This code is not currently used but is left in, commented, as it is
        # likely to be needed again sometime.
        # if message.body == 'Connect':
        #     # Send the settings to that device incase it missed anything
        #     queryset = device.event_defs.all()
        #     serializer = EventDefinitionSerializer(queryset, many=True)
        #     body = {"event_defs": [dict(x) for x in serializer.data]}
        #     listener.broker_interface.send_message("settings", body, device=device)
        #     logger.info("Sent settings message to {}".format(str(device.id)))

    except exceptions.WorkerFoundNoSuchDevice:
        logger.exception("unable to update online status for device")


@decorators.action_handler(name="activity")
def activity_stream_handler(message, listener=None, action_args=None, event_def=None):
    device_activity(message.device, action_args)


@decorators.activity_notifier_handler(name="email")
def user_email_activity_notifier(user, action, device=False,
            organization=False, activity_stream=False):

    subject = "Alert from {d.product.name} {d.id} in {o.name}".format(
                    d=device, o=organization)

    substitutions = {
        "device": {
            "id": str(device.id),
            "name": device.name,
        },
        "product": {
            "id": str(device.product.id),
            "name": device.product.name
        },
        "organization": {
            "id": str(organization.id),
            "name": organization.name
        },
        "device_orgs":[
            {"id": str(o.id), "name": o.name} for o in device.notify_organizations
        ],
        "severity": action.data["severity"],
        "action_description": action.description,
        "account_link": "https://{}/account".format(getattr(settings, "FRONTEND_DOMAIN","")),
        "site": "https://{}".format(getattr(settings, "FRONTEND_DOMAIN","")),
        "site_name": getattr(settings, "SITE_NAME","zconnect"),
        "subject": subject,
    }

    logger.debug("email content %s", substitutions)

    comms.send_email([user],
                     subject,
                     'zconnect-action-alert',
                     substitutions)
    return True


@decorators.activity_notifier_handler(name="sms")
def user_sms_activity_notifier(user, action, device=False, \
            organization=False, activity_stream=False):
    """Implementation of an `activity_notifier_handler` which sends
    an SMS to a user when called.

    Internally this uses `zconnect.comms.send_sms` which itself uses
    https://pypi.org/project/django-sendsms for broad compatibility.
    See django-sendsms for details of how to configure SMS backends
    """
    site_name = getattr(settings, "SITE_NAME", "ZConnect")
    main_org = device.notify_organizations[0]
    body = "Alert from {sn}, in {o.name}: {msg}".format(
        sn=site_name, o=main_org, msg=action.description)
    comms.send_sms([user], body, from_phone=site_name)


@decorators.message_handler(name="report_state")
def device_state_report_handler(message, listener):
    """Handle a device trying to report it's state

    Todo:
        AWS iot has other error codes for this, copied from HTTP error codes. we
        could do that as well
    """
    try:
        message.device.update_reported_state_from_message(message)
    except exceptions.BadMessageSchemaError:
        logger.exception("Device tried to update state with incorrect schema")

        wrapped = {
            "body": {
                "status": "failure",
                "error": "Invalid message schema",
            },
            "device": message.device,
            "category": "reported_state_failure",
            "timestamp": datetime.datetime.utcnow(),
        }
        response = Message.from_dict(wrapped)
        response.send_to_device()

        raise
    except Exception:
        logger.exception("Unknown error processing")

        wrapped = {
            "body": {
                "status": "failure",
                "error": "Unknown error",
            },
            "device": message.device,
            "category": "reported_state_failure",
            "timestamp": datetime.datetime.utcnow(),
        }
        response = Message.from_dict(wrapped)
        response.send_to_device()

        raise
    else:
        logger.info("successfully processed device reporting state update")

        wrapped = {
            "body": {
                "status": "success",
            },
            "device": message.device,
            "category": "reported_state_success",
            "timestamp": datetime.datetime.utcnow(),
        }
        response = Message.from_dict(wrapped)
        response.send_to_device()
