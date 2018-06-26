import datetime
import itertools
import logging

from dateutil.relativedelta import relativedelta
from django.apps import apps
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from zconnect.models import Organization
from zconnect.zc_billing.util import next_bill_period, period_to_delta
from zconnect.zc_timeseries.models import DeviceSensor, TimeSeriesData

# Ideally we would use a string and not import the BillGenerator directly, but
# there is some weird behaviour with django where you can have an app name with
# a dot in it (eg zconnect.zc_billing) but you can't import a model from that
# module (eg zconnect.zc_billing.BillGenerator) when using a foreign key ref
from .bills import Bill

logger = logging.getLogger(__name__)
one_day = relativedelta(days=1)


class BilledOrganization(Organization):

    """Base class for organizations that can be billed

    This just has a reference to the BillGenerator document which says how the
    bills will be generated for this organization

    Note:
        It was done like this:

        .. code-block:: python

            billed_by = models.OneToOneField(
                BillGenerator,
                models.PROTECT,
                null=True,
                related_name="organization",
            )

        can't do this because 'organization' could refer to ANY organization that
        inherits from this class, so the foreign key would be ambiguous

    Attributes:
        billed_by (BillGenerator): The bill generator that is used to generate
            bills for this Organization
    """

    class Meta:
        proxy = True

    def last_bill(self, before=None):
        """Returns the most recent Bill covering a whole period before a
        certain date.

        Args:
            before (datetime, optional): Get bills before this time, or the
                current date if not specified

        Returns:
            Bill() - if matching object found
            None - otherwise
        """
        before = before or datetime.datetime.utcnow()

        try:
            return Bill.objects.filter(
                generated_by=self.billed_by,
                period_end__lt=before
            ).first()
        except Bill.DoesNotExist:
            logger.debug("No bills for %s", self)
            return None
        except BilledOrganization.billed_by.RelatedObjectDoesNotExist:
            logger.info("Organization '%s' has no bill generator", self)
            return None

    def next_bill_on(self, next_from=None):
        """Returns the date when next bill should be issued.

        If there are no bills, the next bill will be one period from the
        active_from_date

        This does not check to see if there is already a bill scheduled for the
        next billing period, it just returns WHEN the next bill would be

        Args:
            next_from (datetime): When to calculate the next bill from. If None,
                use the current date/time
        """
        now = next_from or datetime.datetime.utcnow()
        last_bill = self.last_bill(before=now)

        if last_bill:
            last_period_end = last_bill.period_end
        else:
            last_period_end = self.billed_by.active_from_date - one_day

        _, next_bill_period_end = next_bill_period(
            self.billed_by.active_from_date,
            self.billed_by.period,
            last_period_end,
        )

        return next_bill_period_end + one_day

    @property
    def billed_devices(self):
        """Return devices billed by this org

        This currently requires it to be a Group, but this is how we're
        implementing the device permissions anyway
        """
        if not isinstance(self, Organization):
            raise ValidationError("billed org must be a group")

        Device = apps.get_model(settings.ZCONNECT_DEVICE_MODEL)
        return Device.objects.filter(orgs__in=[self])

    def devices_active_between(self, start, end):
        """Get all devices which were active during the given period

        This checks to see which devices sent TS data during the given period,
        it does NOT check the 'online'/'connected' status of the device. If they
        don't send data, we don't bill them.

        Todo:
            This is very not optimised

        Args:
            start (datetime): beginning of period
            end (datetime): end of period

        Returns:
            Queryset: devices active during this period
        """
        all_billed_devices = self.billed_devices
        # all sensors on all these devices
        sensors = DeviceSensor.objects.filter(device__in=all_billed_devices)
        # For these devices, filter away ones that don't have TS data between
        # the given start/end
        has_reading = TimeSeriesData.objects.filter(
            sensor__in=sensors,
            ts__gte=start,
            ts__lt=end,
        )
        # Get sensors in this
        # Now filter devices based on ones which have a reading
        active_billed_devices = all_billed_devices.filter(
            sensors__data__in=has_reading,
        ).distinct()

        logger.debug("All billed devices = %s", all_billed_devices.count())
        logger.debug("All active billed devices = %s", active_billed_devices.count())

        return active_billed_devices

    def devices_active_for_bill(self, bill):
        """Return all devices active during the billing period of the given bill

        This just calls devices_active_between
        """
        return self.devices_active_between(
            bill.period_start,
            bill.period_end,
        )

    def generate_outstanding_bills(self):
        """Generate all bills up until the current date"""
        now = datetime.datetime.utcnow()

        bills = []

        for _ in itertools.count():
            try:
                bill = self.create_next_bill()
            except ValidationError:
                # This might happen on the first iteration
                break
            else:
                bills.append(bill)
                if bill.period_end + period_to_delta(self.billed_by.period) > now:
                    break

        logger.info("Generated %d bills for '%s'", len(bills), self)

        for b in bills:
            logger.debug(b.period_end)

        return bills

    def create_next_bill(self):
        """Instantiates a Bill object following the most recently issued one.

        This should probably not be called directly, as it is not well defined
        what it means to try and create a bill after the current date

        Use generate_outstanding_bills instead
        """

        try:
            active_from = self.billed_by.active_from_date
        except BilledOrganization.billed_by.RelatedObjectDoesNotExist as e:
            raise ValidationError("Tried to generate bills for an organization with no billing information") from e

        now = datetime.datetime.utcnow()
        last_bill = self.last_bill(before=now)

        if last_bill:
            logger.debug("Last bill ends %s", last_bill.period_end)
        else:
            logger.debug("No bills for organization")

        last_period_end = (
            last_bill.period_end
            if last_bill else
            active_from - one_day
        )

        period = self.billed_by.period
        new_bill_period_start, new_bill_period_end = (
            next_bill_period(active_from, period, last_period_end)
        )

        # This was done using pending_for_current_period below in the clean()
        # method of the bill but that seems like the wrong way to do it
        if new_bill_period_end > now:
            raise ValidationError("Trying to create a bill that spans the current date")
        elif self.bills_covering_period(new_bill_period_start, new_bill_period_end).count():
            # programming error really, this should not happen
            raise ValidationError("A bill is already active in this period")

        billed_devices = self.devices_active_between(new_bill_period_start,
                                                     new_bill_period_end)

        logger.debug("%s devices active for billing period (%s - %s)",
            billed_devices.count(), new_bill_period_start, new_bill_period_end)

        new_bill = Bill(
            generated_by=self.billed_by,
            period_start=new_bill_period_start,
            period_end=new_bill_period_end,
            paid=False,
        )

        new_bill.save()
        new_bill.devices.set(billed_devices)
        new_bill.save()

        return new_bill

    @classmethod
    def pending_for_current_period(cls, now=None):
        """Get all billed organizations for which the time between the given
        point in time ('now') and the end of the last bill period is greater
        than the billing period - ie, get all organizations for which a new bill
        should be created.

        Todo:
            This could probably be implemented with pure annotations but I can't
            think of a nice way to do it

        Args:
            now (datetime, optional): The point at which to calculate billing
                backwards from. If not specified, use the current date/time.

        Returns:
            generator: organizations for which new bills need to be created
        """
        now = now or datetime.datetime.utcnow()

        # Get last bill for each org
        annotated = cls.objects.annotate(
            last_bill_date=models.Max("billed_by__bills__period_end"),
        )
        # Then filter out the ones where there couldn't be a bill for this
        # period
        filtered = annotated.exclude(
            last_bill_date__gte=now,
        )

        def remove_no_bill(org):
            """If the period_end of the last bill was more than 'period' before
            'now' (week, month, year, day), include this org in the results

            This is what needs to be implemented in the annotate() call
            """
            if org.billed_by.bills.latest().period_end < now - period_to_delta(org.billed_by.period):
                return True
            else:
                return False

        return filter(remove_no_bill, filtered)

    def bill_covering_date(self, dt):
        """Returns the Bill document that covers a particular date.

        Args:
            dt - datetime object to match the date range against

        Returns:
            Bill() - if matching object found
            None - otherwise
        """
        try:
            return Bill.objects.filter(
                generated_by=self.billed_by,
                period_start__lte=dt,
                period_end__gte=dt,
            ).get()
        except Bill.DoesNotExist:
            logger.debug("No bill at %s", dt)
            return None
        except BilledOrganization.billed_by.RelatedObjectDoesNotExist:
            logger.info("Organization '%s' has no bill generator", self)
            return None

    def bills_covering_period(self, start=None, end=None):
        """Get all bills that apply to the given period

        This includes bills that started before 'start' or end after 'end'

        Args:
            start (datetime): beginning of period
            end (datetime): end of period

        Returns:
            Queryset: bills for this org which were active during this period,
                paid or unpaid
        """
        try:
            own = models.Q(generated_by=self.billed_by)
        except BilledOrganization.billed_by.RelatedObjectDoesNotExist:
            # if you try to access a related field then it raises an exception
            # like above rather than just returning None
            logger.info("Organization '%s' has no bill generator", self)
            return Bill.objects.none()

        begins_within = models.Q()
        ends_within = models.Q()

        if start:
            begins_within = models.Q(period_start__gte=start) & models.Q(period_start__lte=end)

        if end:
            ends_within = models.Q(period_end__gte=start) & models.Q(period_end__lte=end)

        return Bill.objects.filter(own & (begins_within | ends_within))
