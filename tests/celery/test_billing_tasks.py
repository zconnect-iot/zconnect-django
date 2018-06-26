from datetime import timedelta
from unittest.mock import patch

from zconnect.testutils.factories import (
    BilledOrganizationFactory, BillFactory, BillGeneratorFactory)
from zconnect.zc_billing.tasks import generate_all_outstanding_bills


class TestBillGeneration:

    def test_no_orgs(self, db):
        """Nothing generated"""
        with patch("zconnect.zc_billing.tasks.BilledOrganization.generate_outstanding_bills") as cmock:
            generate_all_outstanding_bills()

        assert not cmock.called

        with patch("zconnect.zc_billing.tasks.BilledOrganization.generate_outstanding_bills") as cmock:
            generate_all_outstanding_bills(orgs=[])

        assert not cmock.called

    def test_non_billed_org(self, db):
        """There are orgs but without any associated billing"""
        org = BilledOrganizationFactory()

        with patch("zconnect.zc_billing.tasks.BilledOrganization.generate_outstanding_bills") as cmock:
            generate_all_outstanding_bills()

        assert not cmock.called

        with patch("zconnect.zc_billing.tasks.BilledOrganization.generate_outstanding_bills") as cmock:
            generate_all_outstanding_bills(orgs=[org])

        assert not cmock.called

    def test_generate_outstanding_validation_error(self, db):
        """Can handle validation errors"""
        biller = BillGeneratorFactory()
        bill = BillFactory(generated_by=biller)
        org = biller.organization

        with patch("zconnect.zc_billing.tasks.BilledOrganization.generate_outstanding_bills", return_value=[bill]) as cmock:
            bills = generate_all_outstanding_bills()

        assert cmock.called
        assert bills[0] == bill

        with patch("zconnect.zc_billing.tasks.BilledOrganization.generate_outstanding_bills", return_value=[bill]) as cmock:
            bills = generate_all_outstanding_bills(orgs=[org])

        assert cmock.called
        assert bills[0] == bill

    def test_generate_outstanding_actual(self, fake_bill_old):
        """Try actually generating bills, as if we haven't done so for two weeks"""
        generator = fake_bill_old.generated_by
        bills = generate_all_outstanding_bills()

        assert len(bills) == 2
        assert bills[0].generated_by == generator
        assert bills[1].generated_by == generator
        assert bills[0].period_start == fake_bill_old.period_end + timedelta(days=1)
        assert bills[1].period_start == bills[0].period_end + timedelta(days=1)
