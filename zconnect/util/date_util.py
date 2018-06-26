from datetime import datetime, timedelta

from dateutil.relativedelta import relativedelta


class InvalidDates(Exception):
    pass


def validate_dates(start=None, end=None, default_period_days=1):
    """
    Takes start, end query parameters and returns valid start, end dates.

    Validation includes:
        - If missing end and start, set end to now.
        - If missing end and has start, set end to:
                min(now, start+default_period_days)
        - If missing start subtract default_period_days from end.
        - end > start : or Raise

    Args:
        start (str - bson $date) - Beginning date period to access data
        end (str - bson $date) -  End date period to access date.
        default_period_days (int=1) - how long to search in the past for TS data

    Raises:
        InvalidDates - if the dates are invalid.
    """
    def time_converter(t):
        # Convert query param to utc time.
        # TODO: Is this the best way of doing this?!
        # Doesn't seem very robust; is relying on the fact the bson ignores
        # microseconds and converts to integer.
        return datetime.utcfromtimestamp(0.001*float(t))

    try:
        if not end and not start:
            valid_end = datetime.utcnow()
            valid_start = valid_end - relativedelta(days=default_period_days)

        elif not end and start:
            valid_start = time_converter(start)
            if valid_start > datetime.utcnow():
                raise InvalidDates("Start time is in the future.")
            valid_end = min(
                datetime.utcnow(),
                valid_start + relativedelta(days=default_period_days))

        elif end and not start:
            valid_end = time_converter(end)
            valid_start = valid_end - relativedelta(days=default_period_days)

        elif start and end:
            valid_start = time_converter(start)
            valid_end = time_converter(end)
            if start >= end:
                raise InvalidDates("Start time is after end time.")

    except Exception as e:
        raise InvalidDates(e) from e

    return valid_start, valid_end


def round_down_time(dt, round_to=60):
    """Round a datetime object to any time laps in seconds

    Args:
        dt (datetime.time): datetime to round
        round_to (int, optional): seconds to round to

    Returns:
        TYPE: Description
    """
    seconds = (dt.replace(tzinfo=None) - dt.min).seconds
    rounding = (seconds // round_to) * round_to
    return dt + timedelta(0, rounding - seconds, -dt.microsecond)

def get_now_timestamp():
    return datetime.utcnow().timestamp()
