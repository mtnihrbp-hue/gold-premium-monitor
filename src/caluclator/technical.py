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
