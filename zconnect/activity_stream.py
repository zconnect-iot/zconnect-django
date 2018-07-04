import logging

from actstream import action as action_model

from zconnect.models import ActivitySubscription
from zconnect.registry import get_activity_notifier_handler

logger = logging.getLogger(__name__)


def device_activity(device, activity):
    """Save a device action to the activity stream and notifies any users that
    are subscribed to this activity.

    This uses `action.send` from the `django_activity_stream` library to save
    the action where the device as both the actor and the target.

    The `activity` dictionary should have the following keys:
    * `verb` - The verb identifies what action was performed by the actor
    * `description` - Description is used in the notification message sent to
        users who have subscribed to this activity. It can use aggregated data
        from the context variable `ctx`, e.g.
        "Message with aggregated data: {ctx.sum_3600_sensor}"
    * `notify` - This will be boolean for if notifications should be attempted
    * `severity` - Numerical severity level, which follows the python logging
        level pattern one of [0, 10, 20, 30, 40, 50]
    * `category` - The category the action belongs to e.g. "business metric"

    `verb` and `description` are accessed on the action object (instance of
    the `Action` model from `actstream.models`) via `action.verb` and
    `action.description`.

    `notify`, `severity` and `category` are accessed via the data jsonfield on
    the action object, `action.data["notify"]`, `action.data["severity"]` and
    `action.data["category"]`
    """
    activity["description"] = activity["description"].format(ctx=device.get_context())
    (_, saved_action) = action_model.send(device, target=device, **activity)[0]
    if saved_action.data["notify"]:
        activity_subscription_notfication(saved_action, device)


def get_all_related_orgs(orgs):
    """ Takes a list of organizations and returns a list of these
    organizations and all other organizations in the parental tree, sorted by
    ascendingly in the list by parental depth. It is assumed that all
    organizations only have one parent but the number of generations is
    unbounded.
    """
    parental_orgs = {}
    for org in orgs:
        parent_depth = 1
        while hasattr(org, 'parent') and org.parent:
            if parent_depth not in parental_orgs:
                parental_orgs[parent_depth] = []
            parental_orgs[parent_depth].append(org.parent)
            org = org.parent
            parent_depth += 1
    # List is in order of parental depth
    for parent_depth in parental_orgs:
        orgs += parental_orgs[parent_depth]
    return orgs


def activity_subscription_notfication(action, device):
    """ Function which takes an action and a device, finds all of the users who
    need to be notified by searching through the activity subscriptions and
    calls the relevant activity notifiers. Each user is only notified once for
    the organization with the lowest parental depth in the organization family
    tree. The function only queries the database once for performance and sorts
    the results in the order that organizations are returned from
    `get_all_related_orgs`. """
    # So that we only alert users once
    alerted_users = {}
    orgs = get_all_related_orgs(device.notify_organizations)
    subscriptions = list(ActivitySubscription.objects.filter(
        organization__in=orgs,
        category=action.data["category"],
        min_severity__lt=action.data["severity"],
    ))
    orgs = [org.id for org in orgs]
    # Sorting by order of parental depth so only "youngest" org is used in
    # notification
    subscriptions.sort(key=lambda sub: orgs.index(sub.organization.id))
    for sub in subscriptions:
        user_id = sub.user.id
        if user_id not in alerted_users or sub.type not in alerted_users[user_id]:
            handler = get_activity_notifier_handler(sub.type)
            result = alerted_users[user_id] if user_id in alerted_users else {}
            try:
                handler(sub.user, action, device, sub.organization)
                result[sub.type] = True
            except Exception: # pylint: disable=broad-except
                logger.exception("%s handler failed to send notification to user %s", sub.type, user_id)
                result[sub.type] = False
            # Please note that django JSONField will convert integer keys into strings
            alerted_users[user_id] = result
    action.data["success"] = alerted_users
    action.save()
