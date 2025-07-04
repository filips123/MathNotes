from datetime import datetime


def parse_datetime(value: str, fmt: str = "%Y-%m-%d %H:%M:%S") -> datetime:
    """Parse a datetime string into a datetime object."""

    return datetime.strptime(value, fmt)


def format_datetime(value: datetime, fmt: str = "%d. %m. %Y, %H:%M:%S") -> str:
    """Format a datetime object into a string."""

    return value.strftime(fmt)
