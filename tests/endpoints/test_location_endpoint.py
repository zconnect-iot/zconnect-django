import math

import pytest

from zconnect.testutils.factories import LocationFactory
from zconnect.testutils.helpers import paginated_body
from zconnect.testutils.util import assert_successful_edit, model_to_dict


class TestLocationEndpoint:
    route = "/api/v3/locations/"

    @pytest.mark.usefixtures("joeseed_login")
    def test_get_locations(self, testclient, fakelocation):
        """Get expected location"""
        expected = {
            "status_code": 200,
            "body": paginated_body([model_to_dict(fakelocation)]),
        }
        testclient.get_request_test_helper(expected)

    @pytest.mark.usefixtures("joeseed_login")
    def test_get_multiple_locations(self, testclient, fakelocation):
        """Get all locations

        This should work just because the second location was added after
        fakelocation and there's no ordering. If ordering is applied in future
        this just needs changing so the order is correct.
        """
        other_location = LocationFactory(locality="Secret lab")
        expected = {
            "status_code": 200,
            "body": paginated_body([
                model_to_dict(fakelocation),
                model_to_dict(other_location),
            ]),
        }
        testclient.get_request_test_helper(expected)

    # TODO
    # paging?
    # filtering?


@pytest.mark.usefixtures("admin_login")
class TestCreateLocationEndpoint:
    route = "/api/v3/locations/"

    def test_create_new_location(self, testclient, adminuser, joeseed):
        """Create a new location and return it - timezone should be
        automatically updated if an empty one is passed"""
        new_location = LocationFactory()
        new_location.delete()

        location_as_dict = model_to_dict(new_location)
        location_as_dict.update({"created_at": None, "updated_at": None})

        post_body = location_as_dict.copy()
        post_body["timezone"] = ""

        expected = {
            "status_code": 201,
            "body": location_as_dict,
        }
        testclient.post_request_test_helper(post_body, expected)

    def test_create_multiple(self, testclient, adminuser, joeseed):
        """Can't create multiple fields at once

        This might change if the serializer is set to accept it...?
        """
        new_location = LocationFactory()
        new_location.delete()

        location_as_dict = model_to_dict(new_location)
        location_as_dict["timezone"] = ""

        post_body = location_as_dict.copy()

        post_body = [
            post_body,
            post_body,
        ]

        expected = {
            "status_code": 400,
            "body": {
                "non_field_errors": [
                    "Invalid data. Expected a dictionary, but got list."
                ]
            }
        }
        testclient.post_request_test_helper(post_body, expected)

    def test_create_missing_fields(self, testclient, joeseed):
        """Missing field -> error"""
        new_location = LocationFactory()
        new_location.delete()

        location_as_dict = model_to_dict(new_location)
        location_as_dict["timezone"] = ""

        post_body = location_as_dict.copy()
        del post_body["country"]

        expected = {
            "status_code": 400,
            "body": {
                "country": [
                    "This field is required."
                ]
            }
        }
        testclient.post_request_test_helper(post_body, expected)

    @pytest.mark.parametrize("latitude, longitude, which_bad", (
        (-91, 0, "latitude"),
        (91, 0, "latitude"),
        (0, 181, "longitude"),
        (0, -181, "longitude"),
    ))
    def test_create_bad_latlong(self, testclient, joeseed, latitude, longitude, which_bad):
        """Invalid lat/long fails"""
        new_location = LocationFactory()
        new_location.delete()

        location_as_dict = model_to_dict(new_location)
        location_as_dict["timezone"] = ""

        post_body = location_as_dict.copy()
        post_body["latitude"] = latitude
        post_body["longitude"] = longitude

        expected = {
            "status_code": 400,
            "body": {
                which_bad: None,
                # Ideally would do this, but would result in lots of copied code
                # "latitude": [
                #     "Ensure this value is less than or equal to 90.0."
                # ]
            }
        }
        testclient.post_request_test_helper(post_body, expected)

    @pytest.mark.parametrize("latitude, as_str", (
        (math.nan, "NaN"),
        (math.inf, "Infinity"),
    ))
    def test_create_invalid_latlong(self, testclient, joeseed, latitude, as_str):
        """Invalid lat/long fails"""
        new_location = LocationFactory()
        new_location.delete()

        location_as_dict = model_to_dict(new_location)
        location_as_dict["timezone"] = ""

        post_body = location_as_dict.copy()
        post_body["latitude"] = latitude

        expected = {
            "status_code": 400,
            "body": {
                "detail": "JSON parse error - Out of range float values are not JSON compliant: '{}'".format(as_str)
            }
        }
        testclient.post_request_test_helper(post_body, expected)

    def test_cannot_delete_all(self, testclient, fakelocation):
        """Can't delete all locations"""
        expected = {
            "status_code": 405,
            "body": {
                "detail": "Method \"DELETE\" not allowed."
            }
        }
        testclient.delete_request_test_helper(expected)


class TestPermissions:
    route = "/api/v3/locations/"

    def test_unauthenticated_post_failure(self, testclient, joeseed):
        """attempt to create new location without logging in"""
        new_location = LocationFactory()
        new_location.delete()

        location_as_dict = model_to_dict(new_location)
        location_as_dict["timezone"] = ""

        post_body = location_as_dict.copy()

        expected = {
            "status_code": 401,
            "body": {
                "detail": "Authentication credentials were not provided."
            }
        }
        testclient.post_request_test_helper(post_body, expected)

    # TODO
    # more permissions checking


@pytest.mark.usefixtures("admin_login")
class TestModifyLocationEndpoint:
    route = "/api/v3/locations/{location_id}/"

    def test_update_existing_location(self, testclient, fakelocation):
        """Update one field"""
        params = {"location_id": fakelocation.id}
        assert_successful_edit(testclient, fakelocation, params, "country", "Bolivia")

    def test_patch_invalid_position_fails(self, testclient, fakelocation):
        """Posting invalid latitude returns an error"""
        path_params = {
            "location_id": fakelocation.id
        }

        post_body = {
            "latitude": 12134343,
        }
        expected = {
            "status_code": 400,
            "body": {
                "latitude": [
                    "Ensure this value is less than or equal to 90.0."
                ]
            },
        }
        testclient.patch_request_test_helper(post_body, expected, path_params=path_params)

    def test_put_requires_all_fields(self, testclient, fakelocation):
        """This test a bit superfluous, just make sure a 'put' requires all fields"""
        path_params = {
            "location_id": fakelocation.id
        }

        # As expected
        expected = {
            "status_code": 200,
            "body": model_to_dict(fakelocation)
        }
        testclient.get_request_test_helper(expected, path_params=path_params)

        # Change country
        after_update_location = model_to_dict(fakelocation)
        after_update_location["country"] = "Bolivia"
        after_update_location.update({"updated_at": None})

        post_body = {
            "country": "Bolivia",
        }
        expected = {
            "status_code": 400,
            "body": {
                "region": [
                    "This field is required."
                ],
                "postalcode": [
                    "This field is required."
                ]

            }
        }
        testclient.put_request_test_helper(post_body, expected, path_params=path_params)

        # Post with all should work
        post_body = after_update_location
        expected = {
            "status_code": 200,
            "body": after_update_location
        }
        testclient.put_request_test_helper(post_body, expected, path_params=path_params)

        # Expect it to change
        expected = {
            "status_code": 200,
            "body": after_update_location
        }
        testclient.get_request_test_helper(expected, path_params=path_params)

    def test_delete_specific_location(self, testclient, fakelocation):
        """Delete one"""
        # First one, shouldn't return the other one
        expected = {
            "status_code": 204,
        }
        path_params = {
            "location_id": fakelocation.id
        }
        testclient.delete_request_test_helper(expected, path_params=path_params)


class TestSpecificLocationEndpoint:
    # TODO
    # Move this to above class when we have permissions set up maybe
    route = "/api/v3/locations/{location_id}/"

    @pytest.mark.usefixtures("joeseed_login")
    def test_get_specific_location(self, testclient, fakelocation):
        other_location = LocationFactory(locality="Secret lab")

        # First one, shouldn't return the other one
        expected = {
            "status_code": 200,
            "body": model_to_dict(fakelocation),
        }
        path_params = {
            "location_id": fakelocation.id
        }
        testclient.get_request_test_helper(expected, path_params=path_params)

        # And the other one
        expected = {
            "status_code": 200,
            "body": model_to_dict(other_location),
        }
        path_params = {
            "location_id": other_location.id
        }
        testclient.get_request_test_helper(expected, path_params=path_params)
