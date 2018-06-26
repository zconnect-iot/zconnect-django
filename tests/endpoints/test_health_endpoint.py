from unittest.mock import patch


class TestHealthEndpoint:
    route = "/api/v3/health/"

    @patch("zconnect.views.check_redis", return_value=False)
    @patch("zconnect.views.check_db", return_value=True)
    def test_redis_down(mock1, mock2, self, testclient):
        expected = {
            "status_code": 500,
            "body": {
                "database_ok": True,
                "redis_ok": False,
            }
        }
        testclient.get_request_test_helper(expected)


    @patch("zconnect.views.check_redis", return_value=True)
    @patch("zconnect.views.check_db", return_value=False)
    def test_db_down(mock3, mock4, self, testclient):
        expected = {
            "status_code": 500,
            "body": {
                "database_ok": False,
                "redis_ok": True,
            }
        }
        testclient.get_request_test_helper(expected)


    @patch("zconnect.views.check_redis", return_value=True)
    @patch("zconnect.views.check_db", return_value=True)
    def test_all_good(mock3, mock4, self, testclient):
        expected = {
            "status_code": 200,
            "body": {
                "database_ok": True,
                "redis_ok": True,
            }
        }
        testclient.get_request_test_helper(expected)
