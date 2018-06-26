import pytest

from zconnect.activity_stream import device_activity
from zconnect.serializers import ActivitySubscriptionSerializer
from zconnect.testutils.helpers import paginated_body


class TestDeviceActivity:
    route = "/api/v3/devices/{device_id}/activity_stream"

    def setup(self):
        self.activity = {
            "severity": 30,
            "description": "Device was open for less than 10% of the time",
            # The following fields are stored in `data` JSONField
            "category": "business metric",
            "notify": False,
            "verb": "reported",
        }

    @pytest.mark.usefixtures("joeseed_login")
    def test_device_activity_stream(self, testclient, fakedevice):
        """ Test that multiple actions in a devices activity stream are
        returned"""
        pp = {
            "device_id": fakedevice.id,
        }
        activity = self.activity
        # Number of actions to create in devices activity stream
        num_actions = 5
        for i in range(num_actions):
            # Create device activity that is saved to database as an `Action`
            device_activity(fakedevice, activity)
        activity["created_at"] = None
        expected = {
            "status_code": 200,
            "body": paginated_body([activity] * num_actions),
        }
        testclient.get_request_test_helper(expected, path_params=pp)

    @pytest.mark.usefixtures("joeseed_login")
    def test_device_activity_stream_filtering(self, testclient, fakedevices):
        """ Test that activity stream is filtered by device """
        pp = {
            "device_id": fakedevices[0].id,
        }
        activity = self.activity
        # Create activity streams for multiple devices
        for fakedevice in fakedevices:
            device_activity(fakedevice, activity)
        activity["created_at"] = None
        # Should only return activity stream for device defined in path_params
        expected = {
            "status_code": 200,
            "body": paginated_body([activity]),
        }
        testclient.get_request_test_helper(expected, path_params=pp)


class TestUserSubscriptions:
    route = "/api/v3/users/{user_id}/subscriptions"

    def test_user_subscriptions(self, testclient, fake_activity_subscription, joeseed_login):
        """ Test a users subscription is returned """
        pp = {
            "user_id": joeseed_login.id,
        }
        activity_subscription = ActivitySubscriptionSerializer(fake_activity_subscription).data

        expected = {
            "status_code": 200,
            "body": [activity_subscription],
        }
        testclient.get_request_test_helper(expected, path_params=pp)

    def test_post_user_subscriptions(self, testclient, joeseed_login, fake_org):
        """ Test a users subscription is returned """
        pp = {
            "user_id": joeseed_login.id,
        }

        post_body = {
            "organization": {
                "id": fake_org.id,
                "name": fake_org.name
            },
            "category": "business metrics",
            "min_severity": 20,
            "type": "sms"
        }

        expected = {
            "status_code": 201,
            "body": {**post_body, **{"id": 1}},
        }
        testclient.post_request_test_helper(post_body, expected, path_params=pp)

    def test_user_cannot_create_duplicate_subscriptions(self, testclient, joeseed_login, fake_org):
        """ Test a users subscription is returned """
        pp = {
            "user_id": joeseed_login.id,
        }

        post_body = {
            "organization": {
                "id": fake_org.id,
                "name": fake_org.name
            },
            "category": "business metrics",
            "min_severity": 20,
            "type": "sms"
        }

        expected = {
            "status_code": 201,
            "body": {**post_body, **{"id": 1}},
        }
        testclient.post_request_test_helper(post_body, expected, path_params=pp)

        expected = {
            "status_code": 400,
            "body": {
                "detail": "Cannot add duplicate subscription",
                "code": "duplicate_activity_subscription"
            },
        }
        testclient.post_request_test_helper(post_body, expected, path_params=pp)


class TestSpecificUserSubscription:
    route = "/api/v3/users/{user_id}/subscriptions/{activity_subscription_id}"

    def test_user_subscriptions(self, testclient, fake_activity_subscription, joeseed_login):
        """ Test a users subscription is returned """
        pp = {
            "user_id": joeseed_login.id,
            "activity_subscription_id": fake_activity_subscription.id,
        }
        activity_subscription = ActivitySubscriptionSerializer(fake_activity_subscription).data

        expected = {
            "status_code": 200,
            "body": activity_subscription,
        }
        testclient.get_request_test_helper(expected, path_params=pp)

    def test_put_user_subscriptions(self, testclient, fake_activity_subscription, joeseed_login, fake_org, fake_org_2):
        """ Test a users subscription is returned """
        pp = {
            "user_id": joeseed_login.id,
            "activity_subscription_id": fake_activity_subscription.id,
        }
        # test changing of org
        post_body = {
            "organization": {
                "id": fake_org_2.id,
                "name": fake_org_2.name
            },
            "category": "Another category",
            "min_severity": 30,
            "type": "push"
        }
        expected = {
            "status_code": 200,
            "body": {**post_body, **{"id": 1}},
        }
        testclient.put_request_test_helper(post_body, expected, path_params=pp)

    def test_patch_user_subscriptions(self, testclient, fake_activity_subscription, joeseed_login, fake_org, fake_org_2):
        """ Test a users subscription is returned """
        pp = {
            "user_id": joeseed_login.id,
            "activity_subscription_id": fake_activity_subscription.id,
        }
        # test changing of org
        post_body = {
            "organization": {
                "id": fake_org_2.id,
                "name": fake_org_2.name
            },
            "category": "Another category",
            "min_severity": 30,
        }
        expected = {
            "status_code": 200,
            "body": {**post_body, **{"id": 1, "type": "email"}},
        }
        testclient.patch_request_test_helper(post_body, expected, path_params=pp)

    def test_delete_user_subscriptions(self, testclient, fake_activity_subscription, joeseed_login):
        """ Test a users subscription is returned """
        pp = {
            "user_id": joeseed_login.id,
            "activity_subscription_id": fake_activity_subscription.id,
        }
        testclient.delete_request_test_helper(path_params=pp)
