"""Local-time conversion, defined once.

Every timestamp this system stores is UTC: the scheduled runner writes UTC and the
database keeps UTC. Every reader of its output is in Iran. Those two facts were
never reconciled, so anything that grouped readings "by day" grouped them by a UTC
day running 03:30 to 03:30 in the reader's own clock, and anything that printed a
time printed it 3.5 hours earlier than the reader's watch.

A fixed offset rather than a timezone database: Iran abolished daylight saving in
2022 and has been a constant UTC+3:30 since, and the tz database is not reliably
present on every runner this code executes on.

This module holds no imports from the rest of the project so that collection,
analysis and presentation can all depend on it without inverting any layering.
"""

from datetime import datetime, timedelta

TEHRAN_UTC_OFFSET = timedelta(hours=3, minutes=30)


def to_tehran(value):
    """Convert a naive UTC timestamp to Iran local time.

    None passes through so callers can convert optional values without guarding
    every call site. An aware value is normalised to UTC first.
    """
    if value is None:
        return None
    if value.tzinfo is not None:
        value = value.replace(tzinfo=None) + value.utcoffset()
    return value + TEHRAN_UTC_OFFSET


def to_utc(value):
    """Inverse of to_tehran, for turning a local calendar boundary into a query bound."""
    return None if value is None else value - TEHRAN_UTC_OFFSET


def local_date(value):
    """The calendar date a stored timestamp falls on, in the reader's own clock."""
    local = to_tehran(value)
    return None if local is None else local.date()


def local_now(now=None):
    """Current local time. `now` is a naive UTC value, for tests."""
    return to_tehran(now if now is not None else datetime.utcnow())
