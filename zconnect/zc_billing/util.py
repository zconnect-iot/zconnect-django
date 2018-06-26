from collections import namedtuple as T
import logging

from dateutil.relativedelta import relativedelta

logger = logging.getLogger(__name__)


periods = ("weekly", "monthly", "yearly")
BillingPeriod = T('BillingPeriod', periods)(*periods)


one_day = relativedelta(days=1)


def next_bill_period(active_from, period, last_period_end):
    logger.debug("Calculating next bill: active from %s", active_from)
    return (
        last_period_end + one_day,
        last_period_end + one_day + period_to_delta(period) - one_day
    )


def period_to_delta(period):
    if period == BillingPeriod.weekly:
        return relativedelta(days=7)
    elif period == BillingPeriod.monthly:
        return relativedelta(months=1)
    elif period == BillingPeriod.yearly:
        return relativedelta(years=1)
    else:
        raise ValueError("Period has to be one of: {}"
                         .format(", ".join(BillingPeriod)))
