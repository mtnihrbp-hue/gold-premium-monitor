"""Size by the drivers: the dollar's trend, world gold's trend, and 18K's own (SP-D, 2026-10-04).

18K is world gold x the dollar, give or take the platforms' gap. 2026-06-16 -> 10-03 rose
on the dollar (+67%, world gold -4%); 2026-01-29 -> 06-16 fell on world gold (-19.7%, the
dollar -2.2%). A driver is DOWN when it is below its 50-day average and its 50-day is
falling over 10 days; a down state counts only after CONFIRM consecutive days, and ends
after CONFIRM days back up, so one bad day does not move the account.

Share in gold by the number of drivers down (dollar, world gold, 18K): SIZES[k].
Daric's 0.30% round trip, one trade a day, signal at i, trade at i+1. Against holding.
"""
import json
import os
import sys
from bisect import bisect_right
from datetime import date

import numpy as np
import talib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
from timeutil import persian_quarter

T = json.load(open(os.path.join(HERE, "data", "tgju_history.json")))


def series(k):
    rows = T[k]
    return [date.fromisoformat(r["date"]) for r in rows], np.array([float(r["close"]) for r in rows])


gd, gc = series("geram18")
ud, uc = series("price_dollar_rl")
xd, xc = series("ons")
n = len(gc)
usd = np.array([uc[bisect_right(ud, d) - 1] for d in gd])
xau = np.array([xc[bisect_right(xd, d) - 1] for d in gd])


def down_state(a, confirm):
    s50 = talib.SMA(a, 50)
    raw = np.array([i >= 60 and a[i] < s50[i] and s50[i] < s50[i - 10] for i in range(len(a))])
    state, run, out = False, 0, np.zeros(len(a), bool)
    for i in range(len(a)):
        if raw[i] != state:
            run += 1
            if run >= confirm:
                state, run = raw[i], 0
        else:
            run = 0
        out[i] = state
    return out


def simulate(sizes, confirm, lo, hi, cost=0.30):
    down = down_state(usd, confirm).astype(int) + down_state(xau, confirm).astype(int) + down_state(gc, confirm).astype(int)
    idx = [i for i in range(n - 1) if lo <= gd[i] <= hi and i >= 260]
    half = cost / 200
    gold, cash, vals, trades = 0.0, 1.0, [], 0
    for k in range(len(idx) - 1):
        i, j = idx[k], idx[k + 1]
        target = sizes[down[i]]
        buy, sell = gc[j] * (1 + half), gc[j] * (1 - half)
        value = cash + gold * sell
        share = gold * sell / value
        if abs(target - share) >= 0.1 or k == 0:
            want, have = target * value, gold * sell
            if want > have:
                spend = min(cash, want - have)
                gold, cash = gold + spend / buy, cash - spend
            else:
                q = (have - want) / sell
                gold, cash = gold - q, cash + q * sell
            trades += 1
        vals.append((gd[j], cash + gold * sell))
    return vals, trades


def quarters(vals):
    out, start_v, cur, last = {}, vals[0][1], None, vals[0][1]
    for day, v in vals:
        q = persian_quarter(day)[2]
        if q != cur:
            if cur is not None:
                out[cur] = last / start_v - 1
                start_v = last
            cur = q
        last = v
    out[cur] = last / start_v - 1
    return out


SPANS = (("2014-23", date(2014, 1, 1), date(2023, 12, 31)), ("2024-26", date(2024, 1, 1), date(2027, 1, 1)),
         ("2026 drop", date(2026, 1, 29), date(2026, 6, 16)), ("01-29->10-01", date(2026, 1, 29), date(2026, 10, 1)))
print("share in gold with 0 / 1 / 2 / 3 drivers down")
for sizes in ((1, 1, 1, 1), (1, 1, 0.6, 0), (1, 0.8, 0.4, 0), (1, 1, 0.4, 0), (1, 0.8, 0.6, 0.2), (1, 1, 1, 0)):
    for confirm in (3, 5):
        row = []
        for span, lo, hi in SPANS:
            vals, trades = simulate(sizes, confirm, lo, hi)
            i0, i1 = gd.index(vals[0][0]), gd.index(vals[-1][0])
            hold = gc[i1] / gc[i0]
            q, qh = quarters(vals), quarters([(gd[i], gc[i] / gc[i0]) for i in range(i0, i1 + 1)])
            ex = [q[k] - qh[k] for k in q if k in qh]
            row.append(f"{span} x{vals[-1][1]:.2f}/{hold:.2f} q{sum(e > .001 for e in ex)}-{sum(e < -.001 for e in ex)} {trades}t")
        print(f"  {str(sizes):22} confirm {confirm}d: " + " | ".join(row))
