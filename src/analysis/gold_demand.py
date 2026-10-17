"""Gold demand: individuals' buying and selling of the gold funds over the last 7 trading days, each
reading set against the past year (SP-D, SP_D_HANDOFF.md sections 35.8-35.11, 46-47). Direction's GOLD
DEMAND section, the evening's GOLD FUNDS block and the room's report read it.

Three readings, from TSETMC's client types summed over the gold funds (saffron excluded):
- money   individuals' net money in, as a multiple of the usual week: the window's buy minus sell
          against `window` times the mean daily net of the 250 trading days before it (the owner,
          2026-10-17: "x times of average"). Undefined when that year was net out, which it was on no
          day since 2019. Until 2026-10-17 the net as a share of buying and selling, which disagreed with
          this on 16% of days (section 46.1); one reading is kept so every message says the same.
- people  buyers a day against the 120 trading days before the window: a rush when many more come
- size    money per buyer against money per seller: below 1, each seller sells more than each buyer buys

Each is ranked against the trailing 250 trading days; the top and bottom 10% are unusual, and the money's
normal range is given as the multiples at those two ends. The readings describe; none is a forecast:
counted by episodes, neither end of the money told what 18K did next (section 46.1), and 19 rushes since
2019 were too few to put a rate on (section 35.10). Calculators calculate: the days come from the caller.
"""

import numpy as np

WINDOW = 7            # the system's 7-day convention (owner, 2026-10-15)
PRIOR = 120           # the people reading's yardstick: the 120 trading days before the window
TRAIL = 250           # the past year, for every rank and for the usual week's money
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


def _finite(x):
    return float(x) if np.isfinite(x) else None


def _readings(window_sums, prior_buyers, usual_daily_net, window):
    bv, bc, sv, sc = window_sums
    money = (bv - sv) / (usual_daily_net * window) if usual_daily_net > 0 else np.nan
    people = (bc / window) / prior_buyers if prior_buyers > 0 else np.nan
    size = (bv / bc) / (sv / sc) if bc and sc and sv else np.nan
    return money, people, size, usual_daily_net * window


def assess(days, sums, window=WINDOW, latest=None):
    """`days` ascending; `sums[k]` = (buy value, buyers, sell value, sellers) of individuals on day k,
    in rial. The latest window's readings, or {} without enough history.

    `latest`, when given, is a window's sums from another source, (buy value, buyers, sell value,
    sellers) over `window` days that follow the history: it is read against the yardsticks at the end of
    `sums` and ranked against its windows, and "as_of" is left to the caller (section 47)."""
    a = np.asarray(sums, dtype=float)
    if len(a) < window + TRAIL + MIN_TRAIL:
        return {}
    net = a[:, 0] - a[:, 2]
    series = []
    for i in range(window + TRAIL - 1, len(a)):
        w = a[i - window + 1:i + 1].sum(axis=0)
        prior = a[i - window - PRIOR + 1:i - window + 1, 1].mean()
        usual = net[i - window - TRAIL + 1:i - window + 1].mean()
        series.append((*_readings(w, prior, usual, window), *w))
    s = np.asarray(series)
    if latest is None:
        history, last = s[-1 - TRAIL:-1], s[-1]
    else:
        w = np.asarray(latest, dtype=float)
        history = s[-TRAIL:]
        last = np.array((*_readings(w, a[-PRIOR:, 1].mean(), net[-TRAIL:].mean(), window), *w))
    bv, bc, sv, sc = last[4:8]
    band = [x for x in history[:, 0] if np.isfinite(x)]
    out = {"as_of": str(days[-1]) if latest is None else None, "window": window,
           "net_rial": float(bv - sv), "buyers_per_day": float(bc / window),
           "usual_rial": _finite(last[3]),
           "band": [float(np.percentile(band, UNUSUAL)), float(np.percentile(band, 100 - UNUSUAL))]
           if len(band) >= MIN_TRAIL else None,
           "per_head_rial": [_finite(bv / bc) if bc else None, _finite(sv / sc) if sc else None]}
    for col, name in enumerate(("money", "people", "size")):
        rank = _rank(history[:, col], last[col])
        out[name] = {"value": _finite(last[col]), "rank": rank, "state": _state(rank)}
    return out
