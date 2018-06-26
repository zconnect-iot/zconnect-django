from django.contrib.auth.hashers import make_password
import pytest

from zconnect.testutils.factories import (
    DeviceFactory, OrganizationFactory, OrganizationMemberFactory, UserFactory)
from zconnect.testutils.helpers import device_to_dict, paginated_body
from zconnect.testutils.util import model_to_dict


class TestDeviceEndpoint:
    route = "/api/v3/devices/"

    def test_get_devices_without_login_fails(self, testclient):
        expected = {
            "status_code": 401,
            "body": {
                "detail": "Authentication credentials were not provided.",
            }
        }
        testclient.get_request_test_helper(expected)

    def test_get_devices_with_login(self, testclient, joeseed):
        expected = {
            "status_code": 200,
            "body": paginated_body([])
        }
        testclient.login(joeseed.username, "test_password")
        testclient.get_request_test_helper(expected)
        testclient.logout()

        expected = {
            "status_code": 401,
            "body": {
                'detail': 'Authentication credentials were not provided.'
            }
        }
        testclient.get_request_test_helper(expected)


@pytest.mark.usefixtures("joeseed_login")
class TestDeviceEndpointLoggedIn:
    route = "/api/v3/devices/"

    def test_get_devices_by_user(self, testclient, fakedevice):
        device = device_to_dict(fakedevice)
        device.update({
            "sensors_current": {},
        })
        expected = {
            "status_code": 200,
            "body": paginated_body([device]),
        }

        qp = {"name": fakedevice.name}

        testclient.get_request_test_helper(expected, query_params=qp)

    def test_get_devices_with_data(self, testclient, fakedevice, fake_ts_data):
        device = model_to_dict(fakedevice)
        # Add latest sensor data to expected results
        sensor_data = model_to_dict(fake_ts_data[0])
        # 'id' and 'sensor' is not returned in serializer
        del sensor_data["id"]
        del sensor_data["sensor"]
        device.update({"sensors_current": {"power_sensor": sensor_data}})
        expected = {
            "status_code": 200,
            "body": paginated_body([device]),
        }
        testclient.get_request_test_helper(expected, expect_identical_values=False)

    def test_no_devices_200(self, testclient, joeseed):
        expected = {
            "status_code": 200,
            "body": paginated_body([])
        }
        testclient.login(joeseed.username, "test_password")
        testclient.get_request_test_helper(expected)

    def test_get_devices_custom_pagination(self, testclient, fakedevices):
        # There are 10 fakedevices, the following custom pagination will return the 4th and 5th
        qp = {
            "page_size": "2",
            "page": "3",
        }
        additional_fields = {
            "sensors_current": {},
        }

        device4 = device_to_dict(fakedevices[4])
        device4.update(additional_fields)
        device5 = device_to_dict(fakedevices[5])
        device5.update(additional_fields)
        expected = {
            "status_code": 200,
            "body": {
                "results": [device4, device5],
                "count": 10,
                "previous": "http://testserver/api/v3/devices/?page=2&page_size=2",
                "next": "http://testserver/api/v3/devices/?page=4&page_size=2",
            }
        }

        testclient.get_request_test_helper(expected, query_params=qp)

    def test_get_stubbed_devices(self, testclient, fakedevice):
        """Stubbing should work on device endpoint"""

        returned = {
            "id": fakedevice.id,
            "name": fakedevice.name
        }

        query_params = {
            "stub": True,
        }
        expected = {
            "status_code": 200,
            "body": paginated_body([returned]),
        }
        testclient.get_request_test_helper(expected, query_params=query_params)


@pytest.mark.usefixtures("admin_login")
class TestDeviceEndpointLoggedInAdmin:
    route = "/api/v3/devices/"

    def test_create_device(self, testclient, fakeproduct):
        device = DeviceFactory(product=fakeproduct)

        device_as_dict = device_to_dict(device)

        unwanted = ["created_at", "updated_at", "last_seen", "id", "product", "sensors_current"]
        for key in unwanted:
            del device_as_dict[key]

        device_as_dict["product"] = fakeproduct.id

        body = device_as_dict.copy()

        device_as_dict.update({
            "id": 2,
            "created_at": None,
            "updated_at": None,
            "last_seen": None,
        })

        expected = {
            "status_code": 201,
            "body": device_as_dict,
        }

        testclient.post_request_test_helper(body, expected)


class TestIndividualDeviceEndpoint:
    route = "/api/v3/devices/{device_id}/"

    @pytest.mark.usefixtures("joeseed_login")
    def test_get_device(self, testclient, fakedevice, fake_ts_data, joeseed):
        device = device_to_dict(fakedevice)
        # Add latest sensor data to expected results
        sensor_data = model_to_dict(fake_ts_data[0])
        del sensor_data["id"]
        del sensor_data["sensor"]

        device.update({
            "sensors_current": {"power_sensor": sensor_data},
        })
        expected = {
            "status_code": 200,
            "body": device,
        }

        path_params = {
            "device_id": fakedevice.id,
        }
        testclient.get_request_test_helper(expected, path_params=path_params)

    def test_update_device(self, testclient, fakedevice, admin_login):
        """Update device owned by user"""
        post_body = {"name": "Joe's device"}

        device = device_to_dict(fakedevice)
        device.update({
            "sensors_current": {},
            "updated_at": None,
        })
        device.update(post_body)

        path_params = {
            "device_id": fakedevice.id,
        }

        expected = {
            "status_code": 200,
            "body": device,
        }
        testclient.patch_request_test_helper(post_body, expected, path_params=path_params)

    def test_get_stubbed_individual_device(self, testclient, fakedevice, joeseed_login):
        """as above"""

        returned = {
            "id": fakedevice.id,
            "name": fakedevice.name
        }

        path_params = {
            "device_id": fakedevice.id,
        }
        query_params = {
            "stub": True,
        }
        expected = {
            "status_code": 200,
            "body": returned,
        }
        testclient.get_request_test_helper(expected, query_params=query_params, path_params=path_params)


class TestOrgPermissions:

    route = "/api/v3/devices/"

    @pytest.fixture(name="org_devices", autouse=True)
    def setup_orgs_and_devices(self, joeseed, fredbloggs):
        """Sets up two orgs and two devices, one of which associated with joe
        and one associated with fred.
        """
        org_joe = OrganizationFactory(name="joe's org")
        org_fred = OrganizationFactory(name="fred's org")

        device_joe = DeviceFactory()
        device_joe.orgs.add(org_joe)
        device_joe.save()

        device_fred = DeviceFactory()
        device_fred.orgs.add(org_fred)
        device_fred.save()

        # This device should never should up except for an admin
        org_random = OrganizationFactory(name="bloart")
        device_random = DeviceFactory()
        device_random.orgs.add(org_random)
        device_random.save()

        OrganizationMemberFactory(
            user=joeseed,
            organization=org_joe,
        )
        OrganizationMemberFactory(
            user=fredbloggs,
            organization=org_fred,
        )

        yield device_joe, device_fred, device_random

    @pytest.mark.usefixtures("joeseed_login")
    def test_joe_one_device(self, testclient, joeseed, org_devices):
        """Make sure joe's device is returned"""

        device_joe, _, _ = org_devices
        device = device_to_dict(device_joe)

        expected = {
            "status_code": 200,
            "body": paginated_body([device])
        }
        testclient.get_request_test_helper(expected)

    @pytest.mark.usefixtures("fredbloggs_login")
    def test_fred_one_device(self, testclient, fredbloggs, org_devices):
        """Make sure joe's device is returned"""

        _, device_fred, _ = org_devices
        device = device_to_dict(device_fred)

        expected = {
            "status_code": 200,
            "body": paginated_body([device])
        }
        testclient.get_request_test_helper(expected)

    @pytest.mark.usefixtures("admin_login")
    def test_admin_both_devices(self, testclient, fredbloggs, org_devices):
        """All devices"""

        expected = {
            "status_code": 200,
            "body": paginated_body([
                device_to_dict(i) for i in org_devices
            ])
        }
        testclient.get_request_test_helper(expected)

    def test_nobody_no_devices(self, testclient, org_devices):
        """No devices for random user"""

        UserFactory(
            first_name="bart",
            last_name="simpson",
            username="bdog@zoetrope.io",
            email="bdog@zoetrope.io",
            password=make_password("test_password")
        )
        testclient.login("bdog@zoetrope.io", "test_password")

        expected = {
            "status_code": 200,
            "body": paginated_body([])
        }
        testclient.get_request_test_helper(expected)
