from unittest.mock import MagicMock, patch

from actstream.models import Action
from organizations.models import Organization
import pytest

from zconnect.activity_stream import get_all_related_orgs
from zconnect.handlers import activity_stream_handler
from zconnect.testutils.factories import ActivitySubscriptionFactory
from zconnect.testutils.fixtures import *


def get_message(device):
    return Message(
        category="event",
        device=device,
        body={},
    )

def mock_get_activity_notifier_handler():
    email_mock = MagicMock()
    sms_mock = MagicMock()
    push_mock = MagicMock()
    values = {"email": email_mock, "sms": sms_mock, "push": push_mock}
    def side_effect(arg):
        return values[arg]
    return side_effect, values

class MockOrg:
    def __init__(self, num_generations, parental_depth=0):
        self.parental_depth = parental_depth
        self.parent = MockOrg(num_generations - 1, parental_depth + 1) if num_generations else False


class TestActivityHandler:
    def test_get_all_related_orgs(self):
        """ Test that `get_all_related_orgs` function returns a list ordered
        ascendingly by parental depth """
        orgs = [MockOrg(2), MockOrg(3), MockOrg(1), MockOrg(0)]
        related_orgs = get_all_related_orgs(orgs)
        assert len(related_orgs) == 10
        parental_depths = [org.parental_depth for org in related_orgs]
        assert parental_depths == [0, 0, 0, 0, 1, 1, 1, 2, 2, 3]

    @pytest.mark.xfail(reason="Depends on RTR specific behaviour. see rtr_django/tests/handlers/test_rtr_activities.py")
    def test_activity_handler_creates_action_and_emails(self, joeseed, fake_device_event_def_activity, fake_site_subsription, simple_ts_data):
        """ Test that activity_stream_handler creates a new action and only
        calls email handler """
        (fakedevice, event_def) = fake_device_event_def_activity
        action_args = event_def.actions["activity"]
        message = get_message(fakedevice)
        side_effect, values = mock_get_activity_notifier_handler()
        with patch("zconnect.activity_stream.get_activity_notifier_handler",
                   side_effect=side_effect):
            activity_stream_handler(message, action_args=action_args)

        new_action = Action.objects.all()[0]
        org = fake_site_subsription.organization
        # Due to a limitation in factory boy need to convert to organization
        # class manually which is the class that django uses
        org.__class__ = Organization
        values["email"].assert_called_once_with(
            joeseed, new_action, fakedevice, org
        )
        values["sms"].assert_not_called()
        values["push"].assert_not_called()

        expect_action_data = {**action_args, **{"success": {}}}
        expect_action_data["success"][str(joeseed.id)] = {"email": True}
        assert new_action.verb == expect_action_data.pop("verb")
        expect_action_data.pop("description")
        assert new_action.description == "Message with aggregation: 6.0"
        assert new_action.data == expect_action_data

    @pytest.mark.xfail(reason="Depends on RTR specific behaviour. see rtr_django/tests/handlers/test_rtr_activities.py")
    def test_activity_handler_filters_by_severity(self, joeseed, fake_device_event_def_activity, fake_site, simple_ts_data):
        """ Test that activity_stream_handler only call handlers when
        min_severity of subscription lower than severity of aciton"""
        (fakedevice, event_def) = fake_device_event_def_activity
        action_args = event_def.actions["activity"]
        # min_severity of subscription greater than action severity of 20
        # should not call email handler
        ActivitySubscriptionFactory(
            type="email", organization=fake_site, min_severity=30
        )
        # min_severity of subscription lower than action severity of 20
        # should call sms handler
        sub = ActivitySubscriptionFactory(
            type="sms", organization=fake_site, min_severity=10
        )
        message = get_message(fakedevice)
        side_effect, values = mock_get_activity_notifier_handler()
        with patch("zconnect.activity_stream.get_activity_notifier_handler",
                   side_effect=side_effect):
            activity_stream_handler(message, action_args=action_args)

        new_action = Action.objects.all()[0]
        org = sub.organization
        # Due to a limitation in factory boy need to convert to organization
        # class manually which is the class that django uses
        org.__class__ = Organization
        values["email"].assert_not_called()
        values["sms"].assert_called_once_with(
            joeseed, new_action, fakedevice, org
        )
        values["push"].assert_not_called()

        expect_action_data = {**action_args, **{"success": {}}}
        expect_action_data["success"][str(joeseed.id)] = {"sms": True}
        assert new_action.verb == expect_action_data.pop("verb")
        expect_action_data.pop("description")
        assert new_action.description == "Message with aggregation: 6.0"
        assert new_action.data == expect_action_data

    @pytest.mark.xfail(reason="Depends on RTR specific behaviour. see rtr_django/tests/handlers/test_rtr_activities.py")
    def test_activity_handler_filters_by_category(self, joeseed, fake_device_event_def_activity, fake_site, simple_ts_data):
        """ Test that activity_stream_handler only call handlers when
        caregory of subscription is equal to category of action"""
        (fakedevice, event_def) = fake_device_event_def_activity
        action_args = event_def.actions["activity"]
        # category not equal to that of action category
        ActivitySubscriptionFactory(
            type="email", organization=fake_site, category="NOT business metric"
        )
        # category equal to that of action category
        sub = ActivitySubscriptionFactory(
            type="push", organization=fake_site, category="business metric"
        )
        message = get_message(fakedevice)
        side_effect, values = mock_get_activity_notifier_handler()
        with patch("zconnect.activity_stream.get_activity_notifier_handler",
                   side_effect=side_effect):
            activity_stream_handler(message, action_args=action_args)

        new_action = Action.objects.all()[0]
        org = sub.organization
        # Due to a limitation in factory boy need to convert to organization
        # class manually which is the class that django uses
        org.__class__ = Organization
        values["email"].assert_not_called()
        values["sms"].assert_not_called()
        values["push"].assert_called_once_with(
            joeseed, new_action, fakedevice, org
        )

        expect_action_data = {**action_args, **{"success": {}}}
        expect_action_data["success"][str(joeseed.id)] = {"push": True}
        assert new_action.verb == expect_action_data.pop("verb")
        expect_action_data.pop("description")
        assert new_action.description == "Message with aggregation: 6.0"
        assert new_action.data == expect_action_data

    @pytest.mark.xfail(reason="Depends on RTR specific behaviour. see rtr_django/tests/handlers/test_rtr_activities.py")
    def test_activity_handler_multiple_users(self, joeseed, fredbloggs, fake_device_event_def_activity, fake_site, fake_company, simple_ts_data):
        """ Test that activity_stream_handler calls handler for each user
        once and uses org with lowest parental depth, in this case site over
        comany for joeseed """
        # Add users to company org
        fake_company.add_user(joeseed)
        fake_company.add_user(fredbloggs)

        (fakedevice, event_def) = fake_device_event_def_activity
        action_args = event_def.actions["activity"]
        # joeseed subscription at site level - will be notified
        joeseed_sub_1 = ActivitySubscriptionFactory(
            user=joeseed, organization=fake_site,
        )
        # joeseed subscription at company level - will NOT be notified as a
        # a joeseed subscription already existing with a org of lower parental
        # depth
        ActivitySubscriptionFactory(
            user=joeseed, organization=fake_company,
        )

        # fredbloggs subscription at company level - will be notified
        fredbloggs_sub = ActivitySubscriptionFactory(
            user=fredbloggs, organization=fake_company,
        )

        message = get_message(fakedevice)
        side_effect, values = mock_get_activity_notifier_handler()
        with patch("zconnect.activity_stream.get_activity_notifier_handler",
                   side_effect=side_effect):
            activity_stream_handler(message, action_args=action_args)

        joeseed_sub_org = joeseed_sub_1.organization
        # Due to a limitation in factory boy need to convert to organization
        # class manually which is the class that django uses
        joeseed_sub_org.__class__ = Organization

        fredbloggs_sub_org = fredbloggs_sub.organization
        fredbloggs_sub_org.__class__ = Organization

        new_action = Action.objects.all()[0]
        values["email"].assert_any_call(
            joeseed, new_action, fakedevice, joeseed_sub_org
        )
        values["email"].assert_any_call(
            fredbloggs, new_action, fakedevice, fredbloggs_sub_org
        )
        values["email"].call_count == 2
        values["sms"].assert_not_called()
        values["push"].assert_not_called()

        expect_action_data = {**action_args, **{"success": {}}}
        # Note both `joeseed` and `fredbloggs` marked as successfully notified
        expect_action_data["success"][str(joeseed.id)] = {"email": True}
        expect_action_data["success"][str(fredbloggs.id)] = {"email": True}
        assert new_action.verb == expect_action_data.pop("verb")
        expect_action_data.pop("description")
        assert new_action.description == "Message with aggregation: 6.0"
        assert new_action.data == expect_action_data
