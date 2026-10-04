"""Paper portfolio, first look: do simple trend rules beat buying and holding 18K? (SP-D)

The owner's idea (2026-10-04): give the system 100M toman, let it buy and sell grams of
18K at most once a day, and judge it quarterly on how much money it ends with. Before
designing that, the honest yardstick: what did buying once and holding do, and what did
the trend rules the R&D tested do, after the cost of a round trip (buy then sell back:
Goldika's buy/sell quotes were 2.37% apart on 2026-10-04 10:35)?

All-in or all-out, one decision per day on the day's close, executed at the next day's
close (no look-ahead). Costs charged as half the round-trip spread on each side.
Periods: 2014-2023 and the 2024-2026 holdout. tgju daily closes.
"""
import json
import os
from datetime import date

import numpy as np
import talib

HERE = os.path.dirname(os.path.abspath(__file__))
rows = json.load(open(os.path.join(HERE, "data", "tgju_history.json")))["geram18"]
d = [date.fromisoformat(r["date"]) for r in rows]
c = np.array([float(r["close"]) for r in rows])
n = len(c)
s50, s200 = talib.SMA(c, 50), talib.SMA(c, 200)
e20, e50 = talib.EMA(c, 20), talib.EMA(c, 50)

# causal 8% ZigZag state: True inside a rally
rally = np.zeros(n, bool)
state, ext = "up", 0
for i in range(n):
    if state == "up":
        if c[i] > c[ext]:
            ext = i
        elif c[i] <= c[ext] * 0.92:
            state, ext = "down", i
    else:
        if c[i] < c[ext]:
            ext = i
        elif c[i] >= c[ext] * 1.08:
            state, ext = "up", i
    rally[i] = state == "up"

RULES = {
    "buy and hold": lambda i: True,
    "above its 50-day": lambda i: c[i] > s50[i],
    "50-day above 200-day": lambda i: s50[i] > s200[i],
    "EMA20 above EMA50": lambda i: e20[i] > e50[i],
    "inside an 8% rally": lambda i: rally[i],
}


def run(rule, lo, hi, spread_pct):
    idx = [i for i in range(n) if lo <= d[i] <= hi and not np.isnan(s200[i])]
    cash, grams, trades, peak, worst = 1.0, 0.0, 0, 1.0, 0.0
    half = spread_pct / 200
    for k in range(len(idx) - 1):
        i, j = idx[k], idx[k + 1]                 # decide on day i, trade at day j's close
        want = rule(i)
        if want and grams == 0:
            grams, cash, trades = cash / (c[j] * (1 + half)), 0.0, trades + 1
        elif not want and grams > 0:
            cash, grams, trades = grams * c[j] * (1 - half), 0.0, trades + 1
        value = cash + grams * c[j] * (1 - half)
        peak = max(peak, value)
        worst = min(worst, value / peak - 1)
    years = (d[idx[-1]] - d[idx[0]]).days / 365.25
    return value, value ** (1 / years) - 1, worst, trades


for lo, hi in ((date(2014, 1, 1), date(2023, 12, 31)), (date(2024, 1, 1), date(2027, 1, 1))):
    print(f"\n{lo.year}-{min(hi.year, 2026)}")
    for spread in (0.0, 1.0, 2.4):
        print(f"  round-trip cost {spread}%")
        for name, rule in RULES.items():
            value, cagr, worst, trades = run(rule, lo, hi, spread)
            print(f"    {name:22} x{value:6.2f}   {cagr * 100:+6.1f}%/yr   worst drawdown {worst * 100:6.1f}%   trades {trades:3}")
