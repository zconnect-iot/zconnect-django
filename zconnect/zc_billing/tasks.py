import datetime
import logging

import celery

from zconnect.zc_billing.models import BilledOrganization

logger = logging.getLogger(__name__)


@celery.shared_task
def generate_all_outstanding_bills(now=None, orgs=None):
    """Generate bills for all organizations, or just the ones passed in

    Args:
        from_date (datetime, optional): When to generate bills up until
        orgs (list(Organization), optional): organizations to generate bills
            for. If not passed in, generate for all organizations that have
            pending bills

    Returns:
        list: list of generated bills

    Todo:
        Return mapping of organization: bills?
    """
    now = now or datetime.datetime.utcnow()

    if not orgs:
        pending = BilledOrganization.pending_for_current_period(now)
    else:
        def filter_with_billing(org):
            try:
                org.billed_by
            except BilledOrganization.billed_by.RelatedObjectDoesNotExist:
                return False
            else:
                return True
        pending = filter(filter_with_billing, orgs)

    pending = list(pending)
    logger.info("Generating bills for %d organizations", len(pending))

    all_bills = []

    for org in pending:
        bills = org.generate_outstanding_bills()

        logger.info("%d bills saved for OrgId=%s:", len(bills), org.id)

        for bn, bill in enumerate(bills):
            logger.debug(
                "Bill %d: %d devices, %f %s, start %s, end %s",
                bn,
                bill.devices.all().count(),
                float(bill.amount)/100.0,
                bill.generated_by.currency,
                datetime.datetime.strftime(bill.period_start, "%d.%m.%Y"),
                datetime.datetime.strftime(bill.period_end, "%d.%m.%Y")
            )

        all_bills.extend(bills)

    return all_bills
