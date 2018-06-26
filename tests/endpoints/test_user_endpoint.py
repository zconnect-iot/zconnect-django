import pytest

from zconnect.serializers import UserSerializer
from zconnect.testutils.helpers import paginated_body
from zconnect.testutils.util import model_to_dict as _model_to_dict


def model_to_dict(model):
    """We serialize the orgs into a list of dicts instead"""
    dumped = _model_to_dict(model)

    serialized = UserSerializer(instance=model).data

    dumped["orgs"] = serialized["orgs"]

    return dumped


class TestUsersEndpoint:
    route = "/api/v3/users/"

    @pytest.mark.usefixtures("admin_login")
    def test_get_all_users(self, testclient, joeseed, adminuser):
        user1 = model_to_dict(joeseed)
        user2 = model_to_dict(adminuser)
        del user1['password'], user2['password']
        del user1['user_permissions'], user2['user_permissions']
        expected = {
            "status_code": 200,
            "body": paginated_body([user2, user1]), # Users are sorted by username
        }

        testclient.get_request_test_helper(expected)

    @pytest.mark.usefixtures("admin_login")
    def test_create_user_with_admin(self, testclient):
        body = {
            "email": "new_user@zoetrope.io",
            "username": "new_user@zoetrope.io",
            "first_name": "new",
            "last_name": "user",
            "password": "test_password",
            "phone_number": "+44 7111 222 333"
        }
        user = body.copy()
        del user["password"]
        user.update(
            {
                "id": None,
                "last_login": None,
                "is_staff": False,
                "is_active": True,
                "is_superuser": False,
                "groups": [],
                "orgs": [],
                "date_joined": None,
                "created_at": None,
                "updated_at": None,
                "phone_number": "+447111222333"
            }
        )
        expected = {
            "status_code": 201,
            "body": user
        }
        testclient.post_request_test_helper(body, expected=expected)

        testclient.logout()
        # Test new password has been set by logging in with it
        testclient.login(body["username"], password=body["password"])



    @pytest.mark.usefixtures("admin_login")
    def test_create_user_invalid_passwords(self, testclient):
        body = {
            "email": "joeseed@zoetrope.io",
            "username": "joeseed@zoetrope.io",
            "first_name": "joe",
            "last_name": "seed",
            "password": "1234",
            "phone_number": "01223123123"
        }
        errors = [
            "This password is too short. It must contain at least 8 characters.",
            "This password is too common.",
            "This password is entirely numeric."
        ]
        expected = {
            "status_code": 400,
            "body": {
                "password": errors
            }
        }
        testclient.post_request_test_helper(body, expected=expected)

        body["password"] = "joeseed@zoetrope.io"

        expected = {
            "status_code": 400,
            "body": {
                "password": [
                    "The password is too similar to the username."
                ]
            }
        }
        testclient.post_request_test_helper(body, expected=expected)

    @pytest.mark.usefixtures("admin_login")
    def test_create_user_invalid_phone_number(self, testclient):
        body = {
            "email": "joeseed@zoetrope.io",
            "username": "joeseed@zoetrope.io",
            "first_name": "joe",
            "last_name": "seed",
            "password": "test_password",
            "phone_number": "ABCD"
        }
        expected = {
            "status_code": 400,
            "body": {
                "phone_number": ['The phone number entered is not valid.']
            }
        }
        testclient.post_request_test_helper(body, expected=expected)

        body["phone_number"] = "1234567"
        expected = {
            "status_code": 400,
            "body": {
                "phone_number": ['The phone number entered is not valid.']
            }
        }
        testclient.post_request_test_helper(body, expected=expected)


class TestUserEndpoint:
    route = "/api/v3/users/{user_id}/"

    @pytest.mark.usefixtures("admin_login")
    def test_get_user_by_id(self, testclient, joeseed):
        pp = {"user_id": str(joeseed.id)}

        user = model_to_dict(joeseed)
        del user['password'], user['user_permissions']
        expected = {
            "status_code": 200,
            "body": user
        }

        testclient.get_request_test_helper(expected, path_params=pp)

    @pytest.mark.usefixtures("admin_login")
    def test_del_user_by_id(self, testclient, joeseed):
        pp = {"user_id": str(joeseed.id)}
        expected = {
            "status_code": 204,
        }
        testclient.delete_request_test_helper(expected=expected, path_params=pp)

    @pytest.mark.usefixtures("admin_login")
    def test_put_user_by_id(self, testclient, joeseed):
        pp = {"user_id": str(joeseed.id)}

        user = model_to_dict(joeseed)
        del user['password'], user['user_permissions']
        user["first_name"] = "test"

        body=user.copy()

        user.update({"updated_at": None})

        expected = {
            "status_code": 200,
            "body": user
        }

        testclient.put_request_test_helper(body, expected=expected, path_params=pp)

    @pytest.mark.usefixtures("admin_login")
    def test_patch_user_by_id(self, testclient, joeseed):
        body={"first_name": "test"}

        pp = {"user_id": str(joeseed.id)}

        user = model_to_dict(joeseed)
        del user['password'], user['user_permissions']
        user.update({"first_name": body["first_name"], "updated_at": None})
        expected = {
            "status_code": 200,
            "body": user
        }

        testclient.patch_request_test_helper(body, expected=expected, path_params=pp)

    @pytest.mark.usefixtures("admin_login")
    def test_patch_user_password(self, testclient, joeseed):
        body={"password": "short"}

        pp = {"user_id": str(joeseed.id)}

        user = model_to_dict(joeseed)
        del user['password'], user['user_permissions']
        user.update({"updated_at": None})
        errors = [
            "This password is too short. It must contain at least 8 characters."
        ]
        expected = {
            "status_code": 400,
            "body": {"password": errors}
        }

        testclient.patch_request_test_helper(body, expected=expected, path_params=pp)

        body={"password": "new_password"}

        expected = {
            "status_code": 200,
            "body": user
        }

        testclient.patch_request_test_helper(body, expected=expected, path_params=pp)
        testclient.logout()

        # Test new password has been set by logging in with it
        testclient.login(joeseed.username, password=body["password"])

    @pytest.mark.xfail(reason="DEFAULT_PERMISSION_CLASSES is an empty array, \
                       remove xfail when permissions have been fully implemented")
    @pytest.mark.usefixtures("joeseed_login")
    def test_attempt_to_change_field_without_permission(self, testclient, joeseed):
        body={"groups": "abc"}

        pp = {"user_id": str(joeseed.id)}

        expected = {
            "status_code": 403,
            "body":   {
                "detail": "You do not have permission to perform this action."
            }
        }

        testclient.patch_request_test_helper(body, expected=expected, path_params=pp)


class TestUserFilter:
    """Test wildcard filters on email/name"""

    route = "/api/v3/users/"

    @pytest.mark.usefixtures("joeseed_login")
    @pytest.mark.parametrize("wildcard", (
        "joe*",
        "*zoetrope.io",
        "*seed@zoe*",
    ))
    def test_filter_by_email(self, testclient, joeseed, wildcard):
        query_params = {
            "email": wildcard,
        }
        expected = {
            "status_code": 200,
            # Don't care about the serialization here, just as long as it
            # returns the right user
            "body": paginated_body([UserSerializer(instance=joeseed).data]),
        }

        testclient.get_request_test_helper(expected, query_params=query_params)

    @pytest.mark.usefixtures("joeseed_login")
    @pytest.mark.parametrize("wildcard", (
        "blo*",
        "*ggs",
        "*log*",
    ))
    def test_filter_by_last_name(self, testclient, fredbloggs, wildcard):
        query_params = {
            "last_name": wildcard,
        }
        expected = {
            "status_code": 200,
            # Don't care about the serialization here, just as long as it
            # returns the right user
            "body": paginated_body([UserSerializer(instance=fredbloggs).data]),
        }

        testclient.get_request_test_helper(expected, query_params=query_params)
