import datetime

from freezegun import freeze_time
import pytest

from zconnect.serializers import StubDeviceSerializer, StubProductSerializer
from zconnect.testutils.factories import BillGeneratorFactory, TimeSeriesDataFactory
from zconnect.testutils.helpers import paginated_body
from zconnect.testutils.util import model_to_dict


def dumpbill(bill):
    bill_body = model_to_dict(bill)
    del bill_body["generated_by"]
    del bill_body["devices"]
    bill_body["amount"] = bill.amount
    bill_body["next_period_end"] = bill.next_period_end.isoformat()
    bill_body["currency"] = bill.generated_by.currency
    bill_body["devices_by_product"] = [
        {
            "devices": [StubDeviceSerializer(d).data for d in x["devices"]],
            "product": StubProductSerializer(x["product"]).data,
        } for x in bill.devices_by_product
    ]
    bill_body["organization"] = {
        "id": bill.generated_by.organization.id,
        "name": bill.generated_by.organization.name,
    }
    return bill_body


class TestDisplayBillDetails:
    route = "/api/v3/bills/{bill_id}/"

    @pytest.mark.usefixtures("admin_login")
    def test_get_specific_bill(self, testclient, fake_bill):
        body = dumpbill(fake_bill)

        assert "id" in body
        assert "created_at" in body
        assert "updated_at" in body
        assert "next_period_end" in body
        assert "period_start" in body
        assert "period_end" in body
        assert "amount" in body
        assert "paid" in body
        assert "currency" in body
        assert "devices_by_product" in body
        assert "organization" in body

        expected = {
            "status_code": 200,
            "body": body
        }
        path_params = {
            "bill_id": fake_bill.id,
        }
        testclient.get_request_test_helper(expected, path_params=path_params)

    def test_get_specific_bill_unauthenticated(self, testclient, fake_bill):
        expected = {
            "status_code": 401,
            "body": {
                "detail": "Authentication credentials were not provided."
            }
        }
        path_params = {
            "bill_id": fake_bill.id,
        }
        testclient.get_request_test_helper(expected, path_params=path_params)

    @pytest.mark.usefixtures("joeseed_login")
    def test_get_specific_bill_not_admin(self, testclient, fake_bill):
        expected = {
            "status_code": 403,
            "body": {
                "detail": "You do not have permission to perform this action."
            }
        }
        path_params = {
            "bill_id": fake_bill.id,
        }
        testclient.get_request_test_helper(expected, path_params=path_params)


class TestUpdateBillDetails:
    route = "/api/v3/bills/{bill_id}/"

    @freeze_time("2018-01-01")
    @pytest.mark.usefixtures("admin_login")
    def test_modify_paid(self, testclient, fake_bill):
        post_body = {
            "paid": True,
        }

        assert not fake_bill.paid

        body = dumpbill(fake_bill)
        body["paid"] = True

        expected = {
            "status_code": 200,
            "body": body
        }
        path_params = {
            "bill_id": fake_bill.id,
        }
        expected["body"]["updated_at"] = datetime.datetime.now().isoformat()
        testclient.patch_request_test_helper(post_body, expected,
                                             path_params=path_params)

    @freeze_time("2018-01-01")
    @pytest.mark.usefixtures("admin_login")
    def test_modify_other_fields(self, testclient, fake_bill):
        post_body = {
            "currency": "USD",
        }

        body = dumpbill(fake_bill)

        expected = {
            "status_code": 200,
            "body": body
        }
        path_params = {
            "bill_id": fake_bill.id,
        }
        expected["body"]["updated_at"] = datetime.datetime.now().isoformat()
        testclient.patch_request_test_helper(post_body, expected,
                                             path_params=path_params)

    @pytest.mark.usefixtures("joeseed_login")
    def test_modify_unauthorised(self, testclient, fake_bill):
        post_body = {
            "paid": True,
        }

        assert not fake_bill.paid

        body = dumpbill(fake_bill)
        body.update(amount=fake_bill.amount)
        body.update(paid=True)

        expected = {
            "status_code": 403,
            "body": {
                "detail": "You do not have permission to perform this action."
            }
        }
        path_params = {
            "bill_id": fake_bill.id,
        }
        testclient.patch_request_test_helper(post_body, expected,
                                             path_params=path_params)


class TestBills:
    route = "/api/v3/bills/"

    @pytest.mark.usefixtures("admin_login")
    def test_get_all_bills_empty(self, testclient):
        expected = {
            "status_code": 200,
            "body": paginated_body([])
        }
        testclient.get_request_test_helper(expected)

    @pytest.mark.usefixtures("admin_login")
    def test_get_a_bill(self, testclient, fake_bill):
        body = dumpbill(fake_bill)
        body.update(amount=fake_bill.amount)

        expected = {
            "status_code": 200,
            "body": paginated_body([body])
        }
        testclient.get_request_test_helper(expected)


class TestBillsByOrg:
    route = "/api/v3/organizations/{org_id}/bills/"

    def test_get_unauthenticated(self, testclient, fake_org):
        """No bills here"""
        expected = {
            "status_code": 401,
            "body": {
                "detail": "Authentication credentials were not provided."
            }
        }
        path_params = {
            "org_id": fake_org.id
        }
        testclient.get_request_test_helper(expected, path_params=path_params)

    @pytest.mark.usefixtures("joeseed_login")
    def test_get_not_admin(self, testclient, fake_org):
        """No bills here"""
        expected = {
            "status_code": 403,
            "body": {
                "detail": "You do not have permission to perform this action."
            }
        }
        path_params = {
            "org_id": fake_org.id
        }
        testclient.get_request_test_helper(expected, path_params=path_params)

    @pytest.mark.usefixtures("admin_login")
    def test_get_no_bills_for_org(self, testclient, fake_org):
        """No bills here"""
        expected = {
            "status_code": 200,
            "body": paginated_body([])
        }
        path_params = {
            "org_id": fake_org.id
        }
        testclient.get_request_test_helper(expected, path_params=path_params)

    @pytest.mark.usefixtures("admin_login")
    @pytest.mark.notavern
    def test_get_bills_for_org_with_generator(self, testclient, fake_org):
        """Generator but still no bill"""
        BillGeneratorFactory(organization=fake_org)

        expected = {
            "status_code": 200,
            "body": paginated_body([])
        }
        path_params = {
            "org_id": fake_org.id
        }
        testclient.get_request_test_helper(expected, path_params=path_params)

    @pytest.mark.usefixtures("admin_login")
    @pytest.mark.notavern
    def test_bill_exists(self, testclient, fake_bill_generator):
        """One bill"""
        fake_org = fake_bill_generator.organization
        bill = fake_org.create_next_bill()
        body = dumpbill(bill)
        # No devices = no cost
        body["amount"] = 0

        expected = {
            "status_code": 200,
            "body": paginated_body([body])
        }
        path_params = {
            "org_id": fake_org.id
        }
        testclient.get_request_test_helper(expected, path_params=path_params)

    @pytest.mark.usefixtures("admin_login")
    @pytest.mark.notavern
    def test_bill_with_devices(self, testclient, fake_bill_generator, fakedevice):
        """One bill"""
        fake_org = fake_bill_generator.organization

        # Create data for device
        fakedevice.orgs.add(fake_org)
        fakedevice.save()

        first_bill = fake_org.create_next_bill()
        first_bill_body = dumpbill(first_bill)
        # Associated device, but it's not active
        first_bill_body["amount"] = 0

        expected = {
            "status_code": 200,
            "body": paginated_body([first_bill_body])
        }
        path_params = {
            "org_id": fake_org.id
        }
        testclient.get_request_test_helper(expected, path_params=path_params)

        # Just after the previous bill
        TimeSeriesDataFactory(
            sensor__device=fakedevice,
            ts=first_bill.period_end + datetime.timedelta(days=1),
        )
        second_bill = fake_org.create_next_bill()
        second_bill_body = dumpbill(second_bill)
        second_bill_body["amount"] = second_bill.amount
        assert second_bill.amount != 0

        expected = {
            "status_code": 200,
            "body": paginated_body([
                # bills are ordered by -period_start, so will always be in this order
                second_bill_body,
                first_bill_body,
            ])
        }
        path_params = {
            "org_id": fake_org.id
        }
        testclient.get_request_test_helper(expected, path_params=path_params)
