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


# -- the Persian (Jalali) calendar -------------------------------------------------------
#
# The paper portfolio's quarters are Persian seasons (owner, 2026-10-04): 1 Farvardin, 1 Tir,
# 1 Mehr and 1 Dey. The arithmetic is the jalaali algorithm (the "breaks" table of years in
# which the 33-year leap cycle shifts), checked against every Persian date tgju publishes
# beside its daily candles. Pure date arithmetic, no tz database.

_JALALI_BREAKS = (-61, 9, 38, 199, 426, 686, 756, 818, 1111, 1181, 1210, 1635, 2060, 2097,
                  2192, 2262, 2324, 2394, 2456, 3178)


def _div(a, b):
    return int(a / b)                      # truncates toward zero, as the algorithm requires


def _mod(a, b):
    return a - _div(a, b) * b


def _jalali_year(jy):
    """(leap, gregorian year, March day of 1 Farvardin) for Jalali year `jy`; leap == 0
    marks a leap year."""
    if not _JALALI_BREAKS[0] <= jy < _JALALI_BREAKS[-1]:
        raise ValueError(f"Jalali year {jy} out of range")
    gy, leap_j, jp, jump = jy + 621, -14, _JALALI_BREAKS[0], 0
    for jm in _JALALI_BREAKS[1:]:
        jump = jm - jp
        if jy < jm:
            break
        leap_j += _div(jump, 33) * 8 + _div(_mod(jump, 33), 4)
        jp = jm
    n = jy - jp
    leap_j += _div(n, 33) * 8 + _div(_mod(n, 33) + 3, 4)
    if _mod(jump, 33) == 4 and jump - n == 4:
        leap_j += 1
    leap_g = _div(gy, 4) - _div((_div(gy, 100) + 1) * 3, 4) - 150
    march = 20 + leap_j - leap_g
    if jump - n < 6:
        n = n - jump + _div(jump + 4, 33) * 33
    leap = _mod(_mod(n + 1, 33) - 1, 4)
    return (4 if leap == -1 else leap), gy, march


def from_jalali(jy, jm, jd):
    """The Gregorian date of Jalali jy/jm/jd."""
    from datetime import date
    _, gy, march = _jalali_year(jy)
    offset = (jm - 1) * 31 - _div(jm, 7) * (jm - 7) + jd - 1
    return date(gy, 3, march) + timedelta(days=offset)


def to_jalali(value):
    """(jy, jm, jd) of a Gregorian date."""
    from datetime import date
    gy = value.year
    jy = gy - 621
    leap, _, march = _jalali_year(jy)
    k = (value - date(gy, 3, march)).days
    if k >= 0:
        if k <= 185:
            return jy, 1 + k // 31, k % 31 + 1
        k -= 186
    else:
        jy -= 1
        k += 179
        if leap == 1:
            k += 1
    return jy, 7 + k // 30, k % 30 + 1


def persian_quarter(value):
    """(first day, last day, label) of the Persian season containing Gregorian date `value`,
    e.g. (2026-09-23, 2026-12-21, "1405 Q3"): seasons start on 1 Farvardin, Tir, Mehr, Dey."""
    jy, jm, _ = to_jalali(value)
    q = (jm - 1) // 3
    first = from_jalali(jy, q * 3 + 1, 1)
    nxt = from_jalali(jy + 1, 1, 1) if q == 3 else from_jalali(jy, q * 3 + 4, 1)
    return first, nxt - timedelta(days=1), f"{jy} Q{q + 1}"
