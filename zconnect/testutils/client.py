import functools
import json
import re
from urllib.parse import parse_qs, urlencode

import pytest
from tavern.testutils.pytesthook import YamlItem
from tavern.util.dict_util import check_keys_match_recursive

from .util import ContextTimer, get_full_route


def print_indent(fmt, *args, **kwargs):
    indented = [re.sub("^", "  ", str(i), flags=re.MULTILINE) for i in args]
    print(fmt.format(*indented, **kwargs))


class BBTestClient:
    def __init__(self, client, route):
        self.std_headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json; charset=utf-8"
        }

        # make sure there is exactly 1 / at the end
        self.route = route.rstrip("/") + "/"

        # Set this value which is set after running a test - this is then
        # checked in the API fixture to make sure that someone didn't forget to
        # actually run a test
        self.test_run = False

        self.logged_in = None

        self.django_client = client

    def assert_response_code(self, result, expected):
        """ Helper to assert that the HTTP response code is as desired """

        __tracebackhide__ = True #pylint: disable=unused-variable

        try:
            desired_code = expected.pop("status_code")
        except KeyError:
            pytest.fail("No status code in expected response")

        if result.status_code != desired_code:
            pytest.fail("Expected status code {}, got '{}'".format(
                desired_code, result.status_code))

    def print_response(self, result):
        print()
        print("Response:")

        print(" Status:")
        print_indent("{}", str(result.status_code))

        print(" Headers:")
        for h, v in dict(result._headers.values()).items():
            print_indent("{}: {}", h, v)

        try:
            returned = result.json()
        except (TypeError, json.decoder.JSONDecodeError):
            body = "<empty>"
        else:
            body = json.dumps(returned, indent=2)

        print(" Body:")
        print_indent("{}", body)
        print()

    def print_request(self, **kwargs):
        print()
        print("Request:")
        print_indent("{} on {}?{}".format(
            kwargs["method"], kwargs["path"], urlencode(kwargs["query_params"])))

        print(" Headers:")
        for k, v in self.std_headers.items():
            print_indent("{}: {}", k, v)

        print(" Query params:")
        for k, v in kwargs["query_params"].items():
            if isinstance(v, bool):
                v = str(v)
            if isinstance(v, list):
                v = ','.join(v)
            print_indent("{}: {}", k, v)

        print(" Body:")
        try:
            print_indent("{}", json.dumps(
                json.loads(kwargs["data"]), indent=2))
        except KeyError:
            print_indent("{}", "<empty>")
        print()

    def check_redirect_params(self, result, expected_redirect_loc,
                              expected_redirect_keys):
        """ Checks the redirect header for the right location and parameters """

        # This will return an empty body if it is just a redirect
        if result.content:
            pytest.fail(
                "Expected empty body on a redirect, but got '{}'".format(result.json()))

        header_dict = {i: j for i, j in result._headers}
        # parse query string and check it's as expected
        uri, query = header_dict["location"].split("?")
        location_keys = parse_qs(query)

        print(" Redirect parameters:")
        for k, v in location_keys.items():
            print_indent("{}: {}", k, v)

        for key in expected_redirect_keys:
            assert expected_redirect_keys[key] == location_keys[key]

        # TODO this should be done in the auth_jwt fixture somehow, but we
        # aren't actually using any redirects in bigbird at the moment so I
        # don't think it matters?
        #if not expected_redirect_loc:
        #    expected_redirect_loc = self.test_jwt_dict[
        #        "redirect_uri"].split("/")[-1]

        endpoint = uri.split("/")[-1]
        assert endpoint == expected_redirect_loc

    def check_expected_keys(self, expected, result, expect_identical_keys, \
            expect_identical_values):

        try:
            returned = result.json()
        except (TypeError, json.decoder.JSONDecodeError):
            returned = {}

        expected_body = expected.pop("body", [{}] if isinstance(returned, list) else {})

        if isinstance(returned, list) and isinstance(expected_body, list):
            bkeys_list = [i.keys() for i in returned]
            ekeys_list = [i.keys() for i in expected_body]
            if len(bkeys_list) != len(ekeys_list):
                pytest.fail("Num of elements in response list ({}) different from num of elements \
                            in expected list ({})".format(len(bkeys_list), len(ekeys_list)))
        elif isinstance(returned, dict) and isinstance(expected_body, dict):
            bkeys_list = [set(returned.keys())]
            ekeys_list = [set(expected_body.keys())]
        else:
            pytest.fail("Type of response ({}) different from type of expected ({})"
                        .format(type(returned).__name__, type(expected_body).__name__))

        for bkeys, ekeys in zip(bkeys_list, ekeys_list):
            bme = bkeys - ekeys
            if bme:
                err = "Found keys {} in response returned which were not expected".format(bme)
                if expect_identical_keys:
                    pytest.fail(err)
                else:
                    print(err)

            emb = ekeys - bkeys
            if emb:
                err = "Found keys {} in expected which were not response returned".format(emb)
                if expect_identical_keys:
                    pytest.fail(err)
                else:
                    print(err)

        # FIXME
        # This api might change in future
        if expect_identical_values:
            check_keys_match_recursive(expected_body, returned, [])

    def login(self, username, password="test_password"):
        """Log in using django test client

        Note that argument could be a variety of things, but for the time being
        this is hardcoded to username/password because that's what we're using
        to log in normally

        Todo:
            Change to email_address

        Args:
            username (str): user name to log in as
            password (str): password to use
        """

        if self.logged_in and (self.logged_in != username):
            pytest.fail("Already logged in as '{}' for this test but you tried to log in as '{}'- this is probably an error where you are trying to use two different login fixtures".format(self.logged_in, username))

        res = self.django_client.login(username=username, password=password)

        if not res:
            pytest.fail("Login failed ({}/{})".format(username, password))

        self.logged_in = username

    def logout(self):
        """Just log out with django test client"""
        self.django_client.logout()
        self.logged_in = None

    # false positive
    # pylint: disable=dangerous-default-value
    def get_request_test_helper(self, expected=None,
            *,
            path_params=None, query_params=None, expect_identical_keys=False,
            expect_identical_values=True, expected_redirect_loc="",
            expected_redirect_keys=None):
        """ Test a get from the API

        Takes various path and query parameters and simulate a request to the
        API, always matching result

        Args:
            expected (dict): Expected result
            path_params: one or more parameters in the path (eg /{user_id})
            query_params (dict): dictionary of things pass in query
                (eg, {a:1, b:2} -> a=b&b=1)
        """

        self.test_run = True

        if not expected:
            expected = {"status_code": 200}

        result = self.simulate_request(
                method="GET",
                path_params=path_params or {},
                query_params=query_params or {})

        # check response code
        self.assert_response_code(result, expected)

        # Whether this has a location header
        has_loc_header = ("location" in (i[0] for i in result._headers))

        if has_loc_header:
            self.check_redirect_params(result, expected_redirect_loc,
                                       expected_redirect_keys or {})

        if result.content:
            self.check_expected_keys(expected, result, expect_identical_keys,
                expect_identical_values)
            # FIXME
            # if it returns a list...?
            #if isinstance(body, dict):
            #    self.check_expected_keys(expected, body, expect_identical_keys,
            #        expect_identical_values)
            #else:
            #    for actual, wanted in zip(body, expected):
            #        assert actual == wanted

        return result

    def _body_required_request_helper(self, method, post_body, expected=None,
                                 *,
                                 path_params=None, query_params=None,
                                 expect_identical_keys=False,
                                 expect_identical_values=True,
                                 expected_redirect_loc="",
                                 expected_redirect_keys=None, **kwargs):
        """ Test a request that requires a body

        Takes various path and query parameters and simulate a request to the
        API, possibly matching result

        Args:
            path_params: one or more parameters in the path (eg /{user_id})
            post_body (dict): dumpable json to send as request body
            expected (dict): Expected result
            query_params (dict): dictionary of things pass in query (eg, a=b&b=1)
            expect_identical_values (bool): Whether to match input to output
            expected_redirect_loc (str): if this was a redirect, where it should
                have been redirected to. it checks the bit after the last  / but
                before the first ?. - eg "http://app.com/oidc/<redirect>?args=..."
            expected_redirect_keys (dict): Expected keys that should have been
                passed along with it if it was a redirect
        """

        if not expected:
            expected = {"status_code": 200}

        self.test_run = True

        result = self.simulate_request(
                method=method,
                data=post_body or {},
                path_params=path_params or {},
                query_params=query_params or {}, **kwargs)

        # check response code
        self.assert_response_code(result, expected)

        # Whether this has a location header
        has_loc_header = ("location" in (i[0] for i in result._headers))

        if has_loc_header:
            self.check_redirect_params(result, expected_redirect_loc,
                                       expected_redirect_keys or {})
        else:
            # Don't do this check if flag is specified
            # if user sends a password, we don't want to send it back for
            # example
            self.check_expected_keys(expected, result, expect_identical_keys,
                expect_identical_values)

        return result

    post_request_test_helper = functools.partialmethod(_body_required_request_helper, "POST")
    put_request_test_helper = functools.partialmethod(_body_required_request_helper, "PUT")
    patch_request_test_helper = functools.partialmethod(_body_required_request_helper, "PATCH")

    def delete_request_test_helper(self, expected=None,
            *,
            path_params=None, query_params=None,
            expected_redirect_loc="", expected_redirect_keys=None):
        """ Delete request """

        if not expected:
            expected = {"status_code": 204}

        if "body" in expected and expected["status_code"] == 204:
            pytest.fail("A successful 'delete' request does not expect any response body")

        self.test_run = True

        result = self.simulate_request(
                method="DELETE",
                path_params=path_params or {},
                query_params=query_params or {})

        # check response code
        self.assert_response_code(result, expected)

        # Whether this has a location header
        has_loc_header = ("location" in (i[0] for i in result._headers))

        if has_loc_header:
            self.check_redirect_params(result, expected_redirect_loc,
                                       expected_redirect_keys or {})
        else:
            # Don't do this check if flag is specified
            # if user sends a password, we don't want to send it back for
            # example
            # FIXME
            #self.check_expected_keys(expected, result, expect_identical_keys,
            #    expect_identical_values)
            pass

        return result

    def simulate_request(self, path_params, query_params, data=None, **kwargs):
        """Simulate request to api

        Args:
            path_params (dict): Path parameters for request
            query_params (dict): Query parameters for request
            data (dict, optional): Body of request
            **kwargs: Any extra parameters to pass to simulate_request - eg
                method

        Returns:
            Result: django result object
        """

        request_args = kwargs

        if "method" not in kwargs:
            pytest.fail("Need method specified for request")

        if data:
            request_args["data"] = json.dumps(data)
        request_args["content_type"] = "application/json; charset=utf-8"

        path = request_args["path"] = get_full_route(path_params, self.route)

        self.print_request(**request_args, query_params=query_params)
        # django test client expects it to be encoded and in wsgi format. no
        # nice parsing like in falcon
        request_args["QUERY_STRING"] = urlencode(query_params)

        # request_args["headers"] = self.std_headers
        # > any HTTP headers in the request are converted to META keys by
        # > converting all characters to uppercase, replacing any hyphens with
        # > underscores and adding an HTTP_ prefix to the name
        # need to do this manually
        for h, v in self.std_headers.items():
            conv = "HTTP_" + h.replace("-", "_").upper()
            request_args[conv] = v

        method = kwargs.pop("method")
        req_method = getattr(self.django_client, method.lower())

        # call it with timer
        with ContextTimer() as t:
            result = req_method(**request_args)

        print("{method:s} on path '{path:s}' took {time:.3f}s".format(
            method=method, path=path, time=t.interval))

        self.print_response(result)

        return result


class WrappedDjangoItem(YamlItem):
    """Dummy just to give it a nice name"""


class TavernClient:

    def __init__(self, request, path):
        """Wrap a single test using a tavern test session

        Everything should be in the global config, no way to get config options
        from 'individual' tests unless we add more fixtures.

        Args:
            request: pytest 'request' fixture
        """
        self.request_args = {}
        self.expected = {}

        self.path = path
        self.nodeid = str(id(request))

        self.request = request
        self.config = request.config
        self.session = request.session
        self.test_name = request.module.__name__
        self.stage_name = request.function.__name__

        self.std_headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json; charset=utf-8"
        }

    def login(self, username, password):
        self.request_args.update({
            "auth": [username, password],
        })

    def logout(self):
        """Only has an effect if we've called 'login' previously"""
        self.request_args.pop("auth", None)

    def _make_request(self, method, expected, body=None, query_params=None, headers=None, path_params=None,
             expect_identical_keys=False,
             expect_identical_values=True):
        """Convert all requests to tavern instead

        Currently requires 'expected' to always be passed

        Todo:
            Take all the parameters as defined in BBTestClient as well
        """
        query_params = query_params or {}
        path_params = path_params or {}
        headers = headers or {}
        body = body or {}

        headers.update(self.std_headers)

        response_body = expected.pop("body", {})

        tavern_block = {
            "test_name": self.test_name,
            "stages": [
                {
                    "name": self.stage_name,
                    "request": {
                        "url": "{host:s}".rstrip("/") + "/" + self.path.format_map(path_params).strip("/") + "/",
                        "method": method.upper(),
                        "headers": headers,
                    },
                    "response": expected,
                }
            ]
        }

        if body:
            tavern_block["stages"][0]["request"]["json"] = body

        if response_body:
            tavern_block["stages"][0]["response"]["body"] = response_body

        if "auth" in self.request_args:
            # Because we are using jwt authentication and session authentication
            # (handled via cookies), we need to add an explicit login step here
            # if the user requested it
            auth = self.request_args.pop("auth")
            auth_stage = {
                "name": "login",
                "request": {
                    "url": "{host:s}".rstrip("/") + "/api/v3/login/",
                    "method": "POST",
                    "json": {
                        "username": auth[0],
                        "password": auth[1],
                    },
                    "headers": {
                        "accepts": "application/json",
                        "content-type": "application/json",
                    }
                },
                "response": {
                    "status_code": 200,
                    "body": {
                        "token_type": "sliding",
                        "token": None,
                    },
                    "save": {
                        "body": {
                            "auth_token": "token"
                        }
                    }
                }
            }

            tavern_block["stages"].insert(0, auth_stage)
            tavern_block["stages"][1]["request"]["headers"]["Authorization"] = "{auth_token:s}"

        # TODO
        # Queue up multiple stages in a test instead of running them all as
        # separate tests. Will require a 'commit' method or something to run at
        # the end

        WrappedDjangoItem(self.test_name, self, tavern_block, self.request.fspath).runtest()

    def _make_body_request(self, method, body, expected, **kwargs):
        self._make_request(method, expected, body=body, **kwargs)

    get_request_test_helper = functools.partialmethod(_make_request, "get")
    delete_request_test_helper = functools.partialmethod(_make_request, "delete")

    post_request_test_helper = functools.partialmethod(_make_body_request, "post")
    patch_request_test_helper = functools.partialmethod(_make_body_request, "post")
    put_request_test_helper = functools.partialmethod(_make_body_request, "post")
