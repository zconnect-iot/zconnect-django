import datetime
from unittest.mock import Mock, patch
import uuid

from django.contrib.auth.models import Group
import pytest
from rest_auth.utils import import_callable


@pytest.mark.notavern
class TestJwtContents:
    route = "/api/v3/auth/login/"

    def test_jwt_correct(self, testclient, joeseed):
        post_body = {
            "username": joeseed.username,
            "password": "test_password",
        }

        fake_token = str(uuid.uuid4())

        expected = {
            "status_code": 200,
            "body": {
                "token": fake_token,
                "token_type": "sliding",
            }
        }

        with patch("rest_framework_simplejwt.backends.jwt.encode",
                Mock(return_value=fake_token.encode("utf8"))) as encode_mock:
            testclient.post_request_test_helper(post_body, expected)

        assert encode_mock.called

    @pytest.mark.parametrize("add_group", (
        True,
        False,
    ))
    def test_jwt_claims(self, testclient, joeseed, add_group, settings):
        """Make sure claims are as expected"""
        post_body = {
            "username": joeseed.username,
            "password": "test_password",
        }

        if add_group:
            fake_group = Group(name="test group")
            fake_group.save()
            joeseed.groups.add(fake_group)
            joeseed.save()
        else:
            fake_group = None

        expected = {
            "status_code": 200,
            "body": {
                "token": None,
                "token_type": "sliding",
            }
        }
        result = testclient.post_request_test_helper(post_body, expected)

        # This might be monkey patched - dynamically import like in the library
        from rest_framework_simplejwt.state import token_backend
        decoded = token_backend.decode(result.json()["token"])

        serializer = import_callable(settings.ZCONNECT_JWT_SERIALIZER)
        expected_serialized = serializer(joeseed).data

        # These two are added manually by us in the serializer
        assert decoded["email"] == expected_serialized["email"] == joeseed.email

        # NOTE
        # not adding groups any more
        # assert len(decoded["groups"]) == len(expected_serialized["groups"]) == len(joeseed.groups.all())
        # if add_group:
        #     # name is the primary key, so this should check correctly
        #     assert decoded["groups"][0]["name"] == expected_serialized["groups"][0]["name"] == list(joeseed.groups.all())[0].name

        assert decoded["token_type"] == "sliding"
        assert decoded["user_id"] == joeseed.id

    @pytest.mark.notavern
    def test_signed_correctly(self, testclient, joeseed, settings):
        """Make sure we can decode the jwt using the """
        post_body = {
            "username": joeseed.username,
            "password": "test_password",
        }

        expected = {
            "status_code": 200,
            "body": {
                "token_type": "sliding",
                "token": None,
            }
        }

        result = testclient.post_request_test_helper(post_body, expected)

        token = result.json()["token"]

        from jwt import decode
        decoded = decode(token, settings.SIMPLE_JWT["VERIFYING_KEY"])

        assert decoded["user_id"] == joeseed.id
        assert decoded["email"] == joeseed.email


class TestRefresh:
    """Make sure getting refresh token works"""

    route = "/api/v3/auth/refresh_token/"

    def test_refresh_bad_jwt(self, testclient):
        """Trying to get a refresh token while sending a bad jwt fails"""

        post_body = {
            "token": "abc"
        }

        expected = {
            "status_code": 401,
            "body": {
                "code": "token_not_valid",
                "detail": "Token is invalid or expired"
            }
        }

        testclient.post_request_test_helper(post_body, expected)

    def generate_jwt(self, user, exp_days, refresh_days):
        from rest_framework_simplejwt.state import token_backend
        # Could also create this with rest_framework_simplejwt.Token()
        raw = {
            "exp": (datetime.datetime.utcnow() + datetime.timedelta(days=exp_days)).timestamp(),
            "refresh_exp": (datetime.datetime.utcnow() + datetime.timedelta(days=refresh_days)).timestamp(),
            "jti": "abc123",
            "token_type": "sliding",
            "user_id": user.id
        }
        return token_backend.encode(raw)


    def test_refresh_correct(self, testclient, joeseed):
        """Correctly pass a valid jwt and return a new one"""

        token = self.generate_jwt(joeseed, 1, 1)

        post_body = {
            "token": token
        }

        expected = {
            "status_code": 200,
            "body": {
                "token": None,
            }
        }

        testclient.post_request_test_helper(post_body, expected)

    def test_expired_token_valid_refresh_claim(self, testclient, joeseed):
        """Send an expired JWT that still has a valid refresh claim and make
        sure we get a valid token back"""

        token = self.generate_jwt(joeseed, -1, 1)

        post_body = {
            "token": token
        }

        expected = {
            "status_code": 200,
            "body": {
                "token": None,
            }
        }

        testclient.post_request_test_helper(post_body, expected)

    def test_expired_refresh_claim_fails(self, testclient, joeseed):

        token = self.generate_jwt(joeseed, -1, -1)

        post_body = {
            "token": token
        }

        expected = {
            "status_code": 401,
            "body": {
                "code": "token_not_valid",
                "detail": "Token 'refresh_exp' claim has expired"
            }
        }

        testclient.post_request_test_helper(post_body, expected)

class TestLoginLogout:

    def _get_client(self, route):
        from rest_framework.test import APIClient
        from zconnect.testutils.client import BBTestClient

        return BBTestClient(APIClient(), "/api/v3/auth/{}".format(route))

    @pytest.mark.xfail(reason="Not a refresh token, and we don't have a logout")
    def test_login_logout(self, client, db, joeseed):
        # FIXME
        # move to tavern once we can do seed data properly
        post_body = {
            "username": joeseed.username,
            "password": "test_password",
        }

        # Log in
        login_client = self._get_client("login")
        expected = {
            "status_code": 200,
            "body": {
                "token": None,
                "token_type": "sliding",
            }
        }
        result = login_client.post_request_test_helper(post_body, expected)

        token = result.json()["token"]

        # Refresh
        refresh_client = self._get_client("refresh")
        refresh_client.std_headers.update({
            "authorization": "Bearer {}".format(token),
        })
        refresh_body = {
            "token": token,
        }
        expected = {
            "status_code": 200,
            "body": {
                "detail": "Successfully logged out."
            }
        }
        refresh_client.post_request_test_helper(refresh_body, expected)

        # Log out
        logout_client = self._get_client("login")
        logout_client.std_headers.update({
            "authorization": "Bearer {}".format(token),
        })
        expected = {
            "status_code": 200,
            "body": {
                "detail": "Successfully logged out."
            }
        }
        logout_client.post_request_test_helper(post_body, expected)
