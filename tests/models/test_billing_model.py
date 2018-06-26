import datetime

import pytest

# from zconnect.testutils.factories import ModelBaseFactory
from zconnect.testutils.factories import (
    BilledOrganizationFactory, BillFactory, BillGeneratorFactory, DeviceFactory,
    DeviceSensorFactory, ProductFactory, TimeSeriesDataFactory)
from zconnect.testutils.util import weeks_ago
from zconnect.zc_billing._models.billed_orgs import BilledOrganization, one_day
from zconnect.zc_billing.util import period_to_delta


@pytest.fixture(name="fake_billed_org")
def fix_fake_billed_org(fake_bill_generator):
    return fake_bill_generator.organization


class TestBilledDevicesQueries:
    """Test the devices_active_between"""

    def _expect_active_devices(self, fake_billed_org, expected):
        start = weeks_ago(3)()
        end = weeks_ago(2)()

        active_1 = fake_billed_org.devices_active_between(start, end)

        bill = BillFactory(
            generated_by=fake_billed_org.billed_by,
            period_start=start,
            period_end=end,
        )

        active_2 = fake_billed_org.devices_active_for_bill(bill)

        assert list(active_1) == list(active_2) == expected

    def test_no_billed_active_no_devices_no_data(self, fake_billed_org):
        """No device, no data"""
        self._expect_active_devices(fake_billed_org, [])

    def test_no_billed_active_devices_no_data(self, fake_billed_org):
        """An 'online' device, but no data"""
        device = DeviceFactory()
        device.orgs.add(fake_billed_org)
        device.online = True
        device.save()

        self._expect_active_devices(fake_billed_org, [])

    def test_billed_active_with_data(self, fake_billed_org):
        """Device with data"""
        device = DeviceFactory()
        device.orgs.add(fake_billed_org)
        device.online = True
        device.save()

        sensor = DeviceSensorFactory(
            device=device,
        )
        TimeSeriesDataFactory(
            sensor=sensor,
            ts=weeks_ago(3)() + datetime.timedelta(days=2)
        )

        self._expect_active_devices(fake_billed_org, [device])

    def test_billed_active_multiple_data_no_repeats(self, fake_billed_org):
        """If there's multiple sensors/ts readings, it should still only return 1 device"""
        device = DeviceFactory()
        device.orgs.add(fake_billed_org)
        device.online = True
        device.save()

        for i in range(3):
            sensor = DeviceSensorFactory(
                device=device,
                sensor_type__sensor_name="Sensor type {}".format(i),
            )
            TimeSeriesDataFactory(
                sensor=sensor,
                ts=weeks_ago(3)() + datetime.timedelta(days=i+1)
            )

        self._expect_active_devices(fake_billed_org, [device])


class TestBillingMethod:

    def test_get_last_bill(self, fake_billed_org):
        assert not fake_billed_org.last_bill()

        # Generate an old bill
        bill_old = BillFactory(generated_by=fake_billed_org.billed_by, period_end=weeks_ago(3)())

        last = fake_billed_org.last_bill()
        assert last == bill_old
        assert last.generated_by == fake_billed_org.billed_by

        # Generate a newer bill - this one should be returned instead
        bill_new = BillFactory(generated_by=fake_billed_org.billed_by, period_end=weeks_ago(1)())

        last = fake_billed_org.last_bill()
        assert last == bill_new
        assert last.generated_by == fake_billed_org.billed_by

    def test_bills_covering_date(self, fake_billed_org):
        two_days_ago = datetime.datetime.utcnow() - datetime.timedelta(days=3)

        # No bill at this date
        assert not fake_billed_org.bill_covering_date(two_days_ago)

        bill = BillFactory(generated_by=fake_billed_org.billed_by, period_start=weeks_ago(1)(), period_end=datetime.datetime.utcnow())

        assert fake_billed_org.bill_covering_date(two_days_ago) == bill

    def test_no_generator_at_date(self, db):
        two_days_ago = datetime.datetime.utcnow() - datetime.timedelta(days=3)

        fake_org = BilledOrganizationFactory()
        # No bill at this date
        assert not fake_org.bill_covering_date(two_days_ago)

    def test_next_bill(self, fake_billed_org):
        """Test period of next bill is 1 day after billing period"""
        assert fake_billed_org.next_bill_on() == fake_billed_org.billed_by.active_from_date + period_to_delta(fake_billed_org.billed_by.period)

        # Generate a bill
        bill = BillFactory(generated_by=fake_billed_org.billed_by, period_end=weeks_ago(2)())

        # The last bill period, plus a week, plus one day (bills are issued one day after the period)
        expected_next_end = bill.period_end + period_to_delta(fake_billed_org.billed_by.period) + one_day

        assert fake_billed_org.next_bill_on(weeks_ago(2)()) == expected_next_end
        # Same if there is no 'next_from' passed, because the last bill will
        # still be the one we generated above
        assert fake_billed_org.next_bill_on() == expected_next_end


class TestCreateBill:

    @pytest.mark.parametrize("n_devices", (
        0,
        1,
        4,
    ))
    def test_create_bill_with_devices(self, fake_billed_org, n_devices):
        """Adds any active devices to the bill, and dynamicaly calculates the amount"""

        for i in range(n_devices):
            device = DeviceFactory()
            device.orgs.add(fake_billed_org)
            device.save()

            TimeSeriesDataFactory(
                sensor__device=device,
                # There is no active bill, so the next bill will be created
                # starting from active_from_date
                ts=fake_billed_org.billed_by.active_from_date + datetime.timedelta(days=i+1)
            )

        bill = fake_billed_org.create_next_bill()

        assert bill.devices.all().count() == n_devices
        assert bill.amount == fake_billed_org.billed_by.rate_per_device*n_devices

    @pytest.mark.parametrize(
        "start, periods", (
            ("2000/1/1", (
                ("2000/1/1", "2000/1/31"),
                ("2000/2/1", "2000/2/29"),
                ("2000/3/1", "2000/3/31"),
            )),
            ("2000/1/29", (
                ("2000/1/29", "2000/2/28"),
                ("2000/2/29", "2000/3/28"),
                ("2000/3/29", "2000/4/28"),
            ))
    ))
    def test_subsequent_monthly_bills_respect_boundary_dates(self, start, periods, db):
        """Bills created in monthly cycles at the end of month should only
        span next full month. E.g:

            * 1-31 Jan, 1-28/29 Feb, 1-31 Mar, ...
            * 29/30/31 Jan - 28/29 Feb, 1-31 Mar, ...

        Copied from zc-thirdparty-billing
        """

        def _get_ymd(dt):
            return dt.year, dt.month, dt.day

        def _s2dt(s):
            y, m, d = _s2ymd(s)
            return datetime.datetime(y, m, d)

        def _s2ymd(s, delim="/"):
            y, m, d = tuple(int(n) for n in s.split(delim))
            return y, m, d

        gen = BillGeneratorFactory(
            period="monthly",
            currency="GBP",
            rate_per_device=1,
            enabled=True,
            active_from_date=_s2dt(start),
        )
        org = BilledOrganizationFactory(
            billed_by=gen,
        )

        (
            (this_start, this_end),
            (next_start, next_end),
            (another_start, another_end)
        ) = periods

        # Create bill under test
        this_but = org.create_next_bill()
        this_but.save()
        assert _get_ymd(this_but.period_start)       == _s2ymd(this_start)
        assert _get_ymd(this_but.period_end)         == _s2ymd(this_end)

        but_next = org.create_next_bill()
        but_next.save()
        assert _get_ymd(but_next.period_start)       == _s2ymd(next_start)
        assert _get_ymd(but_next.period_end)         == _s2ymd(next_end)

        but_another = org.create_next_bill()
        but_another.save()
        assert _get_ymd(but_another.period_start) == _s2ymd(another_start)
        assert _get_ymd(but_another.period_end)   == _s2ymd(another_end)


class TestPendingBills:

    def test_none_pending(self, fake_billed_org):
        """No bills pending at all"""
        assert not list(BilledOrganization.pending_for_current_period())
        assert not list(BilledOrganization.pending_for_current_period(weeks_ago(6)()))

    def test_pending_at_date(self, fake_billed_org):
        """None pending before date was created, but there is one now"""

        BillFactory(
            generated_by=fake_billed_org.billed_by,
            period_start=weeks_ago(7)(),
            period_end=weeks_ago(6)(),
        )

        # There is already a bill for this period
        assert not list(BilledOrganization.pending_for_current_period(weeks_ago(6)()))

        # It has been 6 weeks since the last bill here
        pending = [org for org in BilledOrganization.pending_for_current_period()]
        assert fake_billed_org in pending

    def test_none_future(self, fake_billed_org):
        """It should not return the organization if the last bill was in the
        future"""

        BillFactory(
            generated_by=fake_billed_org.billed_by,
            period_start=weeks_ago(7)(),
            period_end=weeks_ago(6)(),
        )

        assert not list(BilledOrganization.pending_for_current_period(weeks_ago(10)()))


class TestBillPeriods:

    @pytest.fixture(name="fake_bills", autouse=True)
    def fix_create_bills(self, fake_billed_org):
        """Create a couple of bills between 7 and 5 weeks ago"""
        bill_1 = BillFactory(
            generated_by=fake_billed_org.billed_by,
            period_start=weeks_ago(7)(),
            period_end=weeks_ago(6)(),
        )
        bill_2 = BillFactory(
            generated_by=fake_billed_org.billed_by,
            period_start=weeks_ago(6)(),
            period_end=weeks_ago(5)(),
        )

        return bill_1, bill_2

    def test_no_bills_in_period(self, fake_billed_org):
        """Before any bills"""
        assert not list(fake_billed_org.bills_covering_period(
            weeks_ago(11)(),
            weeks_ago(10)(),
        ))

    def test_first_bill(self, fake_billed_org, fake_bills):
        """Includes the tail end of the first bill"""
        bill_1, bill_2 = fake_bills

        assert list(fake_billed_org.bills_covering_period(
            weeks_ago(11)(),
            weeks_ago(7)(),
        )) == [bill_1]

    def test_both_bills_outside_range_below(self, fake_billed_org, fake_bills):
        """both bills, starting before the first one"""
        bill_1, bill_2 = fake_bills

        assert list(fake_billed_org.bills_covering_period(
            weeks_ago(11)(),
            weeks_ago(6)(),
        )) == [bill_2, bill_1]
        # The order here is because bills are ordered by -period_end, so the
        # latest ones are returned from queries first

    def test_both_bills_inside_range(self, fake_billed_org, fake_bills):
        """Inside the range of the bills"""
        bill_1, bill_2 = fake_bills

        assert list(fake_billed_org.bills_covering_period(
            weeks_ago(7)(),
            weeks_ago(6)(),
        )) == [bill_2, bill_1]

    def test_both_bills_outside_range_above(self, fake_billed_org, fake_bills):
        """both bills, ending after the second one"""
        bill_1, bill_2 = fake_bills

        assert list(fake_billed_org.bills_covering_period(
            weeks_ago(7)(),
            weeks_ago(3)(),
        )) == [bill_2, bill_1]

    def test_second_bill(self, fake_billed_org, fake_bills):
        """Only the second one, 'start' is too big to include first one"""
        bill_1, bill_2 = fake_bills

        assert list(fake_billed_org.bills_covering_period(
            weeks_ago(6)(),
            weeks_ago(3)(),
        )) == [bill_2]

    def test_no_bills_after_period(self, fake_billed_org):
        """Only the second one, 'start' is too big to include first one"""

        assert list(fake_billed_org.bills_covering_period(
            weeks_ago(4)(),
            weeks_ago(3)(),
        )) == []


class TestGetDevices:

    def test_devices_grouped(self, fake_billed_org):
        """Get all devices on a bill, grouped by product"""

        devices = []

        for pidx in range(3):
            product = ProductFactory(
                name="Test product {}".format(pidx),
            )

            for didx in range(3):
                device = DeviceFactory(
                    product=product,
                    name="test device {}-{}".format(pidx, didx),
                )
                device.orgs.add(fake_billed_org)
                device.save()

                devices.append(device)

        bill = BillFactory(
            generated_by=fake_billed_org.billed_by,
        )

        bill.devices.set(devices)
        bill.save()

        billed_devices = bill.devices_by_product

        for obj in billed_devices:
            assert "product" in obj
            assert "devices" in obj
