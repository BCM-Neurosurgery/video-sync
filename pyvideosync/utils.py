from datetime import datetime, timedelta


def ts2unix(time_origin, resolution, ts) -> datetime:
    """
    Convert a list of timestamps into Unix timestamps
    based on the origin time and resolution.

    Args:
        time_origin: e.g. datetime.datetime(2024, 4, 16, 22, 7, 32, 403000)
        resolution: e.g. 30000
        ts: e.g. 37347215

    Returns:
        e.g. 2024-04-16 22:28:17.310167
    """
    base_time = datetime(
        time_origin.year,
        time_origin.month,
        time_origin.day,
        time_origin.hour,
        time_origin.minute,
        time_origin.second,
        time_origin.microsecond,
    )
    return base_time + timedelta(microseconds=(ts * 1000000 / resolution))
