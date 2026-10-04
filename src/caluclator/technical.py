"""Technical analysis math over a daily price series (SP-D Direction track).

Deterministic and causal: every value at index i uses only data up to i. Standard
indicators come from TA-Lib, so their definitions are the industry's, not ours; what
TA-Lib does not provide -- support and resistance levels -- is defined here.

A swing high or low needs SWING_WINDOW days on each side to be confirmed, so a swing at
day j is known only from day j + SWING_WINDOW. `swing_levels(..., upto=i)` uses only
swings confirmed by day i. Without that, a level would be drawn from days that had not
happened yet, and every measured hit rate would be flattered by hindsight.
"""

import numpy as np
import talib

MA_PERIODS = (20, 50, 200)
TREND_SLOPE_DAYS = 10          # the 50-day average must have risen over this many days
RSI_PERIOD = 14
SWING_WINDOW = 5               # days on each side of a swing high or low
LEVEL_LOOKBACK_DAYS = 250      # about a year of trading days
LEVEL_CLUSTER_PCT = 2.0        # swings closer than this are one level


def moving_averages(close):
    """{period: array} of simple moving averages; NaN before a full window."""
    values = np.asarray(close, dtype=float)
    return {period: talib.SMA(values, timeperiod=period) for period in MA_PERIODS}


def rsi(close, period=RSI_PERIOD):
    return talib.RSI(np.asarray(close, dtype=float), timeperiod=period)


def _known(value):
    return value is not None and not np.isnan(value)


def trend_state(close, averages, i):
    """UPTREND, DOWNTREND or MIXED at day i, or None before the 200-day average exists.

    UPTREND: price above the 50-day average, the 50-day above the 200-day, and the
    50-day higher than TREND_SLOPE_DAYS ago. DOWNTREND is the mirror. Anything else is
    MIXED: a trend that is forming, fading or absent.
    """
    m50, m200 = averages[50], averages[200]
    if i < TREND_SLOPE_DAYS or not (_known(m50[i]) and _known(m200[i]) and _known(m50[i - TREND_SLOPE_DAYS])):
        return None
    if close[i] > m50[i] > m200[i] and m50[i] > m50[i - TREND_SLOPE_DAYS]:
        return "UPTREND"
    if close[i] < m50[i] < m200[i] and m50[i] < m50[i - TREND_SLOPE_DAYS]:
        return "DOWNTREND"
    return "MIXED"


def stretch_pct(close, averages, i, period=50):
    """How far the price sits from its average, in percent, or None."""
    m = averages[period][i]
    return None if not _known(m) else (close[i] / m - 1) * 100


def swing_levels(high, low, upto, usable=None, lookback=LEVEL_LOOKBACK_DAYS,
                 window=SWING_WINDOW, cluster_pct=LEVEL_CLUSTER_PCT):
    """Support and resistance levels known at day `upto`, nearest first is not implied.

    Swing highs and lows of the last `lookback` days, confirmed by `upto` (a swing at j
    needs j + window <= upto), clustered when within `cluster_pct` of each other.
    `usable[j]` False skips a day whose high and low are not a real range (tgju's flat
    or flagged candles). Returns [{"price", "touches", "last"}] sorted by price, where
    `last` is the index of the most recent swing in the level.
    """
    start = max(window, upto - lookback)
    pivots = []
    for j in range(start, upto - window + 1):
        if usable is not None and not usable[j]:
            continue
        span = range(j - window, j + window + 1)
        if high[j] >= max(high[k] for k in span):
            pivots.append((float(high[j]), j))
        if low[j] <= min(low[k] for k in span):
            pivots.append((float(low[j]), j))

    levels = []
    for price, j in sorted(pivots):
        if levels and abs(price / levels[-1]["price"] - 1) * 100 < cluster_pct:
            level = levels[-1]
            level["price"] = (level["price"] * level["touches"] + price) / (level["touches"] + 1)
            level["touches"] += 1
            level["last"] = max(level["last"], j)
        else:
            levels.append({"price": price, "touches": 1, "last": j})
    return levels


def split_levels(levels, price):
    """(supports below `price` nearest first, resistances above nearest first)."""
    supports = sorted((lv for lv in levels if lv["price"] < price), key=lambda lv: -lv["price"])
    resistances = sorted((lv for lv in levels if lv["price"] >= price), key=lambda lv: lv["price"])
    return supports, resistances


# -- trend legs, levels by time at price, and the clocks (SP-D, SP_D_HANDOFF.md section 4) ---

RALLY_REVERSAL = 0.08          # a rally ends 8% below its peak; a correction ends 8% above its trough
HIGH_LOOKBACK_DAYS = 250       # a "new high" is a new 52-week closing high
ZONE_BIN_PCT = 1.0             # time-at-price bins, 1% wide
ZONE_TOP = 5                   # the five most-visited bins of the last year


def rally_legs(close, reversal=RALLY_REVERSAL):
    """Causal ZigZag. For every day i: (direction, leg_start) as known on day i.

    direction is "up" inside a rally and "down" inside a correction; leg_start is the
    trough (or peak) that began the current leg, confirmed only once the price had moved
    `reversal` away from it -- so the leg a day belongs to never depends on later days.
    """
    c = np.asarray(close, dtype=float)
    n = len(c)
    direction = np.empty(n, dtype=object)
    start = np.zeros(n, dtype=int)
    state, extreme, pivot = "up", 0, 0
    for i in range(n):
        if state == "up":
            if c[i] > c[extreme]:
                extreme = i
            elif c[i] <= c[extreme] * (1 - reversal):
                state, pivot, extreme = "down", extreme, i
        else:
            if c[i] < c[extreme]:
                extreme = i
            elif c[i] >= c[extreme] * (1 + reversal):
                state, pivot, extreme = "up", extreme, i
        direction[i], start[i] = state, pivot
    return direction, start


def days_since_high(close, lookback=HIGH_LOOKBACK_DAYS):
    """Trading days since the last new `lookback`-day closing high (0 on the day of one)."""
    c = np.asarray(close, dtype=float)
    out = np.zeros(len(c), dtype=int)
    for i in range(1, len(c)):
        out[i] = 0 if c[i] >= c[max(0, i - lookback + 1):i + 1].max() else out[i - 1] + 1
    return out


def time_at_price_zones(close, upto, lookback=LEVEL_LOOKBACK_DAYS, bin_pct=ZONE_BIN_PCT, top=ZONE_TOP):
    """The price zones where daily closes clustered most over the last year, known at
    `upto`: a stand-in for a volume profile, since no source publishes volume. Returns
    [{"price", "days"}] for the `top` most-visited `bin_pct` bins."""
    window = np.asarray(close[max(0, upto - lookback + 1):upto + 1], dtype=float)
    if len(window) < 20 or window.min() <= 0:
        return []
    step = np.log1p(bin_pct / 100)
    edges = np.exp(np.arange(np.log(window.min()), np.log(window.max()) + step, step))
    if len(edges) < 3:
        return []
    counts, _ = np.histogram(window, bins=edges)
    order = np.argsort(counts)[::-1][:top]
    return [{"price": float((edges[k] + edges[k + 1]) / 2), "days": int(counts[k])}
            for k in order if counts[k] > 0]


VOLUME_PROFILE_DAYS = 120      # about six months of trading days
VALUE_AREA = 0.70              # the share of the traded value the value area holds


def volume_profile(high, low, close, volume, upto, lookback=VOLUME_PROFILE_DAYS, bin_pct=1.0):
    """Volume at price over the `lookback` days to `upto`: each day's volume spread evenly
    across its low..high range, in `bin_pct` bins. Returns {"poc", "val", "vah"} (the most
    traded price and the value area's low and high edge), or None without volume.

    No platform publishes volume; the gold funds on the Tehran exchange do (TSETMC). Their
    value traded spread over 18K's own daily range is the volume this uses. On 2019-2026
    the value-area edges held as support/resistance 5-18 pp more often than a level with
    no history; the POC alone did not (-19 / +11 pp): SP_D_HANDOFF.md section 11.
    """
    first = max(0, upto - lookback + 1)
    lo_p, hi_p = np.log(np.min(low[first:upto + 1])), np.log(np.max(high[first:upto + 1]))
    step = np.log1p(bin_pct / 100)
    edges = np.arange(lo_p, hi_p + step, step)
    if len(edges) < 3:
        return None
    mass = np.zeros(len(edges) - 1)
    for j in range(first, upto + 1):
        if not volume[j] or volume[j] <= 0:
            continue
        a, b = np.log(min(low[j], close[j])), np.log(max(high[j], close[j]))
        ka = int(np.clip(np.searchsorted(edges, a) - 1, 0, len(mass) - 1))
        kb = int(np.clip(np.searchsorted(edges, b) - 1, ka, len(mass) - 1))
        mass[ka:kb + 1] += volume[j] / (kb - ka + 1)
    if mass.sum() <= 0:
        return None
    mids = np.exp((edges[:-1] + edges[1:]) / 2)
    poc = int(np.argmax(mass))
    lo_k = hi_k = poc
    area = mass[poc]
    while area < VALUE_AREA * mass.sum():
        down = mass[lo_k - 1] if lo_k > 0 else -1.0
        up = mass[hi_k + 1] if hi_k < len(mass) - 1 else -1.0
        if up >= down:
            hi_k += 1
            area += mass[hi_k]
        else:
            lo_k -= 1
            area += mass[lo_k]
    return {"poc": float(mids[poc]), "val": float(mids[lo_k]), "vah": float(mids[hi_k])}


TRENDLINE_LOOKBACK = 120       # trading days the trend lines are drawn from
TRENDLINE_TOLERANCE = 0.005    # a close may pierce the line by 0.5% and it still stands
FIB_RATIOS = (0.236, 0.382, 0.5, 0.618)


def _pivots(values, upto, window, find_high, usable=None, lookback=TRENDLINE_LOOKBACK):
    first = max(window, upto - lookback)
    out = []
    for j in range(first, upto - window + 1):
        if usable is not None and not usable[j]:
            continue
        span = values[j - window:j + window + 1]
        if (find_high and values[j] >= max(span)) or (not find_high and values[j] <= min(span)):
            out.append(j)
    return out


def trendlines(high, low, close, upto, window=SWING_WINDOW, lookback=TRENDLINE_LOOKBACK, usable=None):
    """The support line joining two confirmed swing lows and the resistance line joining two
    confirmed swing highs, as a chartist draws them: of every pair whose line no later close
    crosses (beyond TRENDLINE_TOLERANCE), the support is the one closest under today's
    close and the resistance the one closest over it. Returns {"support", "resistance"},
    each None or {"i1", "y1", "i2", "y2", "slope_pct_per_day", "at": the line's value at
    `upto`}. Causal: a swing counts only once its `window` confirming days have passed."""
    c = np.asarray(close, dtype=float)
    now = c[upto]
    result = {}
    for kind, values, sign in (("support", np.asarray(low, dtype=float), 1),
                               ("resistance", np.asarray(high, dtype=float), -1)):
        piv = _pivots(values, upto, window, find_high=(sign < 0), usable=usable, lookback=lookback)
        best = None
        for b_ in range(1, len(piv)):
            for a_ in range(b_):
                i1, i2 = piv[a_], piv[b_]
                slope = (values[i2] - values[i1]) / (i2 - i1)
                line = values[i1] + slope * (np.arange(i1, upto + 1) - i1)
                closes = c[i1:upto + 1]
                at = line[-1]
                if sign > 0:
                    valid = np.all(closes >= line * (1 - TRENDLINE_TOLERANCE)) and at <= now
                    better = best is None or at > best[3]
                else:
                    valid = np.all(closes <= line * (1 + TRENDLINE_TOLERANCE)) and at >= now
                    better = best is None or at < best[3]
                if valid and better:
                    best = (i1, i2, slope, at)
        if best:
            i1, i2, slope, at = best
            y1 = float(values[i1])
            result[kind] = {"i1": int(i1), "y1": y1, "i2": int(i2), "y2": float(values[i2]),
                            "slope_pct_per_day": float(slope / y1 * 100), "at": float(at)}
        else:
            result[kind] = None
    return result


def fibonacci(swing_low, swing_high, ratios=FIB_RATIOS):
    """Retracement levels of a move from `swing_low` up to `swing_high`: [(ratio, price)]."""
    return [(r, float(swing_high - (swing_high - swing_low) * r)) for r in ratios]
