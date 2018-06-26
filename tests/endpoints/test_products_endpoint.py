from django.conf import settings
from rest_auth.utils import import_callable

from zconnect.testutils.factories import ProductFactory
from zconnect.testutils.helpers import paginated_body
from zconnect.testutils.util import assert_successful_edit


class TestProductsEndpoint:
    route = "/api/v3/products/"

    def setup(self):
        self.product_serializer = import_callable(settings.ZCONNECT_PRODUCT_SERIALIZER)

    def test_get_unauthenticated(self, testclient, fakeproduct):
        """When not logged in you should not be able to see the list of products"""
        expected = {
            "status_code": 401,
            "body": {
                "detail": "Authentication credentials were not provided."
            }
        }
        testclient.get_request_test_helper(expected)

    def test_get_authenticated(self, testclient, fakeproduct, joeseed_login):
        expected = {
            "status_code": 200,
            "body": paginated_body([self.product_serializer(fakeproduct).data]),
        }
        testclient.get_request_test_helper(expected)

    def test_get_admin(self, testclient, fakeproduct, admin_login):
        expected = {
            "status_code": 200,
            "body": paginated_body([self.product_serializer(fakeproduct).data]),
        }
        testclient.get_request_test_helper(expected)

    def test_post_unauthenticated(self, testclient):
        post_body = self.product_serializer(ProductFactory()).data
        expected = {
            "status_code": 401,
            "body": {
                "detail": "Authentication credentials were not provided."
            }
        }
        testclient.post_request_test_helper(post_body, expected)

    def test_post_authenticated(self, testclient, joeseed_login):
        post_body = self.product_serializer(ProductFactory()).data
        expected = {
            "status_code": 403,
            "body": {
                "detail": "Only admins are allowed to modify."
            }
        }
        testclient.post_request_test_helper(post_body, expected)

    def test_post_admin(self, testclient, admin_login):
        new_product = ProductFactory()
        new_product.delete()

        post_body = self.product_serializer(new_product).data
        del post_body["updated_at"], post_body["created_at"],

        product = post_body.copy()
        product.update({"created_at": None, "updated_at": None})

        expected = {
            "status_code": 201,
            "body": product
        }
        testclient.post_request_test_helper(post_body, expected)


class TestProductEndpoint:
    route = "/api/v3/products/{product_id}/"

    def setup(self):
        self.product_serializer = import_callable(settings.ZCONNECT_PRODUCT_SERIALIZER)

    def test_get_unauthenticated(self, testclient, fakeproduct):
        expected = {
            "status_code": 401,
            "body": {
                "detail": "Authentication credentials were not provided."
            }
        }
        path_params = { "product_id": fakeproduct.id }
        testclient.get_request_test_helper(expected, path_params=path_params)

    def test_get_authenticated(self, testclient, fakeproduct, joeseed_login):
        expected = {
            "status_code": 200,
            "body": self.product_serializer(fakeproduct).data
        }
        path_params = { "product_id": fakeproduct.id }
        testclient.get_request_test_helper(expected, path_params=path_params)

    def test_get_admin(self, testclient, fakeproduct, admin_login):
        expected = {
            "status_code": 200,
            "body": self.product_serializer(fakeproduct).data
        }
        path_params = { "product_id": fakeproduct.id }
        testclient.get_request_test_helper(expected, path_params=path_params)

    def test_update_existing_unauthenticated(self, testclient, fakeproduct):
        path_params = { "product_id": fakeproduct.id }
        post_body = { "name": "Super IoT Product" }
        expected = {
            "status_code": 401,
            "body": {
                "detail": "Authentication credentials were not provided."
            }
        }
        testclient.patch_request_test_helper(post_body, expected, path_params=path_params)

    def test_update_existing_authenticated(self, testclient, fakeproduct, joeseed_login):
        path_params = { "product_id": fakeproduct.id }
        post_body = { "name": "Super IoT Product" }
        expected = {
            "status_code": 403,
            "body": {
                "detail": "Only admins are allowed to modify."
            }
        }
        testclient.patch_request_test_helper(post_body, expected, path_params=path_params)

    def test_update_existing_admin(self, testclient, fakeproduct, admin_login):
        params = {"product_id": fakeproduct.id}
        assert_successful_edit(testclient, fakeproduct, params, "name", "Super IoT Product", serializer=self.product_serializer)
