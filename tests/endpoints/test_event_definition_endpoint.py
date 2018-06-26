import pytest

from zconnect.models import EventDefinition
from zconnect.serializers import EventDefinitionSerializer
from zconnect.testutils.factories import (
    DeviceEventDefinitionFactory, DeviceFactory, OrganizationFactory)
from zconnect.testutils.helpers import expect_detail, expect_list, expect_model
from zconnect.testutils.util import assert_successful_edit


class TestEventDefinitionEndpoint:
    route = "/api/v3/devices/{device_id}/event_defs/{event_def_id}/"

    def test_get_no_auth(self, testclient, fake_device_event_definition):
        exp = expect_detail(401,"Authentication credentials were not provided.")
        pp = {
            "device_id": fake_device_event_definition.device.id,
            "event_def_id": fake_device_event_definition.id
        }
        testclient.get_request_test_helper(exp, path_params=pp)

    @pytest.mark.usefixtures("joeseed_login")
    def test_get_authenticated(self, testclient, fake_device_event_definition):
        expected = expect_model(200, fake_device_event_definition,
                                serializer=EventDefinitionSerializer)

        pp = {
            "device_id": fake_device_event_definition.device.id,
            "event_def_id": fake_device_event_definition.id
        }
        testclient.get_request_test_helper(expected, path_params=pp)

    @pytest.mark.usefixtures("joeseed_login")
    def test_get_deleted(self, testclient, fake_device_event_definition):
        fake_device_event_definition.deleted = True
        fake_device_event_definition.save()
        expected = expect_detail(404, "Not found.")
        pp = {
            "device_id": fake_device_event_definition.device.id,
            "event_def_id": fake_device_event_definition.id
        }
        testclient.get_request_test_helper(expected, path_params=pp)

        # Make sure it's still there, just marked as deleted
        event_defs = EventDefinition.objects.all()
        assert event_defs
        assert event_defs[0].deleted == True

    @pytest.mark.usefixtures("fredbloggs_login")
    def test_get_wrong_user(self, testclient, fake_device_event_definition):
        expected = expect_detail(404, "Not found.")
        pp = {
            "device_id": fake_device_event_definition.device.id,
            "event_def_id": fake_device_event_definition.id
        }
        testclient.get_request_test_helper(expected, path_params=pp)

    @pytest.mark.usefixtures("admin_login")
    def test_get_admin(self, testclient, fake_device_event_definition):
        expected = expect_model(200, fake_device_event_definition,
                                serializer=EventDefinitionSerializer)
        pp = {
            "device_id": fake_device_event_definition.device.id,
            "event_def_id": fake_device_event_definition.device.id
        }
        testclient.get_request_test_helper(expected, path_params=pp)

    @pytest.mark.usefixtures("admin_login")
    def test_get_wrong_id(self, testclient, fake_device_event_definition):
        expected = expect_detail(404, "Not found.")
        pp = {
            "device_id": fake_device_event_definition.device.id,
            "event_def_id": 123456
        }
        testclient.get_request_test_helper(expected, path_params=pp)

    @pytest.mark.usefixtures("admin_login")
    def test_update_admin(self, testclient, fake_device_event_definition):
        params = {
            "device_id": fake_device_event_definition.device.id,
            "event_def_id": fake_device_event_definition.id
        }
        assert_successful_edit(testclient,
                               fake_device_event_definition,
                               params,
                               "condition",
                               "a<b",
                               serializer=EventDefinitionSerializer)

    @pytest.mark.usefixtures("joeseed_login")
    def test_update(self, testclient, fake_device_event_definition):
        params = {
            "device_id": fake_device_event_definition.device.id,
            "event_def_id": fake_device_event_definition.id
        }
        assert_successful_edit(testclient,
                               fake_device_event_definition,
                               params,
                               "ref",
                               "newref",
                               serializer=EventDefinitionSerializer)

    @pytest.mark.usefixtures("admin_login")
    def test_delete_admin(self, testclient, fake_device_event_definition):
        params = {
            "device_id": fake_device_event_definition.device.id,
            "event_def_id": fake_device_event_definition.id
        }
        testclient.delete_request_test_helper(path_params=params)

        ed = EventDefinition.objects.get(id=fake_device_event_definition.id)
        assert ed.deleted == True

    @pytest.mark.usefixtures("joeseed_login")
    def test_delete(self, testclient, fake_device_event_definition):
        params = {
            "device_id": fake_device_event_definition.device.id,
            "event_def_id": fake_device_event_definition.id
        }
        testclient.delete_request_test_helper(path_params=params)

        ed = EventDefinition.objects.get(id=fake_device_event_definition.id)
        assert ed.deleted == True

    @pytest.mark.usefixtures("joeseed_login")
    def test_put(self, testclient, fakedevice, fake_device_event_definition):
        pp = {
            "device_id": fakedevice.id,
            "event_def_id": fake_device_event_definition.id
        }

        post_body = {
            "enabled": False,
            "ref": "test_email_ev_def:company",
            "condition": "another_variable_2<another_value_2",
            "actions": {"email": {"alert_text": "There is a problem again!"}},
            "debounce_window": 300,
            "scheduled": True,
            "single_trigger": True,
        }

        expected = {
            "status_code": 200,
            "body": {**post_body, **{
                "id": 1,
                "created_at": None,
                "updated_at": None,
                "product": None,
            }},
        }

        testclient.put_request_test_helper(post_body, expected, path_params=pp)

    @pytest.mark.usefixtures("joeseed_login")
    def test_patch(self, testclient, fakedevice, fake_device_event_definition):
        pp = {
            "device_id": fakedevice.id,
            "event_def_id": fake_device_event_definition.id
        }

        post_body = {
            "enabled": False,
            "ref": "test_email_ev_def:company",
            "condition": "another_variable_2<another_value_2",
            "actions": {"email": {"alert_text": "There is a problem again!"}},
            "debounce_window": 300,
            "scheduled": True,
        }

        expected = {
            "status_code": 200,
            "body": {**post_body, **{
                "id": 1,
                "created_at": None,
                "updated_at": None,
                "product": None,
                "single_trigger": False,
            }},
        }

        testclient.patch_request_test_helper(post_body, expected,
                                             path_params=pp)


class TestEventDefinitionsEndpoint:
    route = "/api/v3/devices/{device_id}/event_defs/"

    def test_get_no_auth(self, testclient, fake_device_event_definition):
        expected = expect_detail(401, "Authentication credentials were not provided.")
        pp = {
            "device_id": fake_device_event_definition.device.id
        }
        testclient.get_request_test_helper(expected, path_params=pp)

    @pytest.mark.usefixtures("joeseed_login")
    def test_get_list(self, testclient, fake_device_event_definition):
        expected = {
            "status_code": 200,
            "body": {
                "count": 1,
                "next": None,
                "previous": None,
                "results": [
                    EventDefinitionSerializer(fake_device_event_definition).data
                ]
            }
        }
        pp = {
            "device_id": fake_device_event_definition.device.id
        }
        testclient.get_request_test_helper(expected, path_params=pp)

    @pytest.mark.usefixtures("joeseed_login")
    def test_get_deleted(self, testclient, fake_device_event_definition):
        fake_device_event_definition.deleted = True
        fake_device_event_definition.save()
        expected = {
            "status_code": 200,
            "body": {
                "count": 0,
                "next": None,
                "previous": None,
                "results": []
            }
        }
        pp = {
            "device_id": fake_device_event_definition.device.id
        }
        testclient.get_request_test_helper(expected, path_params=pp)

    @pytest.mark.usefixtures("fredbloggs_login")
    def test_get_by_reference(self, testclient, fredbloggs):
        device = DeviceFactory()
        event_def_1 = DeviceEventDefinitionFactory(device=device, product=None, ref="abcde")
        event_def_2 = DeviceEventDefinitionFactory(device=device, product=None, ref="bcdef")

        expected = expect_detail(404, "Not found.")
        pp = {"device_id": device.id}
        qp = {"ref": "abcde"}
        testclient.get_request_test_helper(expected, path_params=pp,
                                           query_params=qp)
        group = OrganizationFactory()
        device.orgs.add(group)
        device.save()
        # fredbloggs.orgs.add(group)
        fredbloggs.add_org(group)
        fredbloggs.save()

        data_1 = EventDefinitionSerializer(event_def_1).data
        data_2 = EventDefinitionSerializer(event_def_2).data

        expected = expect_list(200, [data_1])
        pp = {"device_id": device.id}
        qp = {"ref": "abcde"}
        testclient.get_request_test_helper(expected, path_params=pp,
                                           query_params=qp)

        expected = expect_list(200, [data_2])
        qp = {"ref": "*ef"}
        testclient.get_request_test_helper(expected, path_params=pp,
                                           query_params=qp)

        expected = expect_list(200, [data_2])
        qp = {"ref": "bcdef"}
        testclient.get_request_test_helper(expected, path_params=pp,
                                           query_params=qp)

        expected = expect_list(200, [data_1, data_2])
        qp = {"ref": "*cd*"}
        testclient.get_request_test_helper(expected, path_params=pp,
                                           query_params=qp)

        expected = expect_list(200, [])
        qp = {"ref": "xyz"}
        testclient.get_request_test_helper(expected, path_params=pp,
                                           query_params=qp)

    def test_post_event_definition(self, testclient, fakedevice, joeseed_login):
        pp = {"device_id": fakedevice.id}

        post_body = {
            "enabled": True,
            "ref": "test_email_ev_def:site",
            "condition": "another_variable<another_value",
            "actions": {"email": {"alert_text": "There is a problem!"}},
            "debounce_window": 600,
            "scheduled": False,
            "single_trigger": False,
        }

        expected = {
            "status_code": 201,
            "body": {
                **post_body,
                "id": 1,
                "created_at": None,
                "updated_at": None,
                "product": None,
            },
        }

        testclient.post_request_test_helper(post_body, expected,
                                            path_params=pp)
