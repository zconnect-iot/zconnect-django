from timezonefinder import TimezoneFinder


class TzFinderSingleton:
    instance = None

    def __new__(cls):
        if not cls.instance:
            cls.instance = TimezoneFinder()

        return cls.instance


def get_timezone_no_matter_what(lat, lng, max_delta=7):
    """
    Attempt to get a timezone from a location irrespective of where it is.

    If you pass in a point in the middle of the ocean, this will iteratively
    increase the search distance until it finds a timezone or hits the max_delta

    A max_delta of 7 should be enough to get anything in the atlantic or pacific.
    It will however be intensive and would be subject to DOS attacks.

    Arguments:
        lat (int, str): Latitude
        lng (int, str): Longitude
        max_delta (int): The maximum distance from the location in degrees

    Returns:
        str: timezone e.g. "Europe/London" or None if the max_delta is reached
    """
    tz_finder = TzFinderSingleton()
    # pylint: disable=maybe-no-member
    tz = tz_finder.timezone_at(
        lng=lng,
        lat=lat
    )

    delta = 1

    while tz is None and delta <= max_delta:
        # pylint: disable=maybe-no-member
        tz = tz_finder.closest_timezone_at(
            lng=lng,
            lat=lat,
            delta_degree=delta
        )
        delta += 1

    return tz
