"""Gold demand: individuals' buying and selling of the gold funds over the last 7 trading days, each
reading set against the past year (SP-D, SP_D_HANDOFF.md sections 35.8-35.11). Direction's GOLD DEMAND
section reads it.

Three readings, from TSETMC's client types summed over the gold funds (saffron excluded):
- money   individuals' net money in, as a share of their buying and selling: (buy - sell) / (buy + sell)
- people  buyers a day against the 120 trading days before the window: a rush when many more come
- size    money per buyer against money per seller: below 1, each seller sells more than each buyer buys

Each is ranked against the trailing 250 trading days; the top and bottom 10% are unusual. Measured on
2017-2026: each reading flags 6-12% of days at each end, and money catches what the other two miss --
the net 39,268 B toman of May 2026 and the exodus of December 2025. The readings describe; none is a
forecast: counted by episodes, 19 rushes since 2019 were too few to put a rate on (section 35.10).
Calculators calculate: the days come from the caller.
"""

import numpy as np

WINDOW = 7            # the system's 7-day convention (owner, 2026-10-15)
PRIOR = 120           # the people reading's yardstick: the 120 trading days before the window
TRAIL = 250           # the past year, for every rank
MIN_TRAIL = 100
UNUSUAL = 10          # percent at each end
MIN_FUNDS = 14        # a day counts when this many of the 18 funds have it


def _rank(history, value):
    h = np.asarray([x for x in history if np.isfinite(x)])
    return float(np.mean(h < value) * 100) if len(h) >= MIN_TRAIL and np.isfinite(value) else None


def _state(rank):
    if rank is None:
        return None
    return "HIGH" if rank >= 100 - UNUSUAL else "LOW" if rank < UNUSUAL else "NORMAL"


def assess(days, sums):
    """`days` ascending; `sums[k]` = (buy value, buyers, sell value, sellers) of individuals on day k,
    in rial. The latest window's readings, or {} without enough history."""
    a = np.asarray(sums, dtype=float)
    if len(a) < WINDOW + PRIOR + MIN_TRAIL:
        return {}
    series = []
    for i in range(WINDOW + 59, len(a)):
        bv, bc, sv, sc = a[i - WINDOW + 1:i + 1].sum(axis=0)
        prior = a[max(0, i - WINDOW - PRIOR + 1):i - WINDOW + 1, 1]
        money = (bv - sv) / (bv + sv) if bv + sv else np.nan
        people = (bc / WINDOW) / prior.mean() if prior.mean() > 0 else np.nan
        size = (bv / bc) / (sv / sc) if bc and sc and sv else np.nan
        series.append((money, people, size, bv, bc, sv))
    s = np.asarray(series)
    last = s[-1]
    out = {"as_of": str(days[-1]), "window": WINDOW,
           "net_rial": float(last[3] - last[5]), "buyers_per_day": float(last[4] / WINDOW)}
    for col, name in enumerate(("money", "people", "size")):
        rank = _rank(s[-1 - TRAIL:-1, col], last[col])
        out[name] = {"value": float(last[col]), "rank": rank, "state": _state(rank)}
    return out
