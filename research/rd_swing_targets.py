"""The owner's own example as a rule: "buys at 26.77, sells at 27.00, then buys back at
26.50" (2026-10-04). A held core plus a swing part: sell the swing at +TAKE over its entry,
buy it back RE_BUY under the sale price, or after MAX_OUT days (never miss the trend for
long). Core out only on v0's confirmed break. (SP-D)

Daily closes, signal at day i, trade at day i+1, one trade a day, continuous shares.
Costs: Daric 0.30%, Goldika 2.37% round trip. In-sample 2014-2023, holdout 2024-2026.
"""
import itertools
import json
import os
import sys
from datetime import date

import numpy as np
import talib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
from timeutil import persian_quarter

rows = json.load(open(os.path.join(HERE, "data", "tgju_history.json")))["geram18"]
d = [date.fromisoformat(r["date"]) for r in rows]
c = np.array([float(r["close"]) for r in rows])
n = len(c)
e20, e50, s50 = talib.EMA(c, 20), talib.EMA(c, 50), talib.SMA(c, 50)
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


def run(lo, hi, cost, core, take, re_buy, max_out, use_break=True):
    idx = [i for i in range(n) if lo <= d[i] <= hi and i >= 260]
    half = cost / 200
    gold, cash, entry, sold_at, out_since = 0.0, 1.0, None, None, None
    core_out, trades, vals = False, 0, []
    for k in range(len(idx) - 1):
        i, j = idx[k], idx[k + 1]
        broke = (not rally[i]) and c[i] < s50[i]
        back = (c[i] > s50[i] and e20[i] > e50[i]) or (rally[i] and not rally[i - 1])
        core_out = use_break and ((core_out or broke) and not back)
        buy, sell = c[j] * (1 + half), c[j] * (1 - half)
        value = cash + gold * sell
        share = gold * sell / value
        if core_out:
            target = 0.0
        elif sold_at is None:
            # swing held: take the profit at +take over its entry
            target = core if entry and c[i] >= entry * (1 + take / 100) else 1.0
        else:
            # swing sold: buy back re_buy under the sale, or after max_out days
            target = 1.0 if (c[i] <= sold_at * (1 - re_buy / 100) or k - out_since >= max_out) else core
        if abs(target - share) > 0.05:
            want, have = target * value, gold * sell
            if want > have:
                spend = min(cash, want - have)
                gold += spend / buy
                cash -= spend
                entry, sold_at, out_since = c[j], None, None
            else:
                q = (have - want) / sell
                gold -= q
                cash += q * sell
                if target > 0:
                    sold_at, out_since = c[j], k
            trades += 1
        elif entry is None and share > 0.5:
            entry = c[j]
        vals.append((d[j], cash + gold * sell))
    return vals, trades


def quarters(vals):
    out, start_v, cur, last = {}, vals[0][1], None, vals[0][1]
    for day, v in vals:
        qq = persian_quarter(day)[2]
        if qq != cur:
            if cur is not None:
                out[cur] = last / start_v - 1
                start_v = last
            cur = qq
        last = v
    out[cur] = last / start_v - 1
    return out


def compare(vals, base):
    q, qb = quarters(vals), quarters(base)
    ex = [q[k] - qb[k] for k in q if k in qb]
    return sum(e > 0.001 for e in ex), sum(e < -0.001 for e in ex), np.mean(ex) * 100


for cost, venue in ((0.30, "Daric"), (2.37, "Goldika")):
    print(f"\n######## {venue} ({cost}% round trip)")
    spans = ((date(2014, 1, 1), date(2023, 12, 31)), (date(2024, 1, 1), date(2027, 1, 1)))
    bases = [run(lo, hi, cost, 1.0, 1e9, 0, 1, use_break=False)[0] for lo, hi in spans]
    v0 = [run(lo, hi, cost, 1.0, 1e9, 0, 1)[0] for lo, hi in spans]
    print(f"  buy and hold: x{bases[0][-1][1]:.2f} / x{bases[1][-1][1]:.2f}   v0 (confirmed break only): x{v0[0][-1][1]:.2f} / x{v0[1][-1][1]:.2f}")
    res = []
    for core, take, re_buy, max_out, ub in itertools.product((0.6, 0.8), (1, 2, 3, 5, 8), (1, 2, 3), (5, 10, 20), (True, False)):
        v, t = run(*spans[0], cost, core, take, re_buy, max_out, ub)
        res.append((v[-1][1], (core, take, re_buy, max_out, ub), t))
    res.sort(key=lambda x: -x[0])
    for value, params, t in res[:4]:
        v2, t2 = run(*spans[1], cost, *params)
        a, b = compare(run(*spans[0], cost, *params)[0], bases[0]), compare(v2, bases[1])
        core, take, re_buy, max_out, ub = params
        print(f"    core {core:.0%}{' +break' if ub else ''}, sell swing at +{take}%, buy back -{re_buy}% or {max_out}d | 2014-2023 x{value:.2f} "
              f"(q {a[0]}-{a[1]}, {a[2]:+.1f} pp, {t / 10:.0f} trades/yr) | 2024-2026 x{v2[-1][1]:.2f} (q {b[0]}-{b[1]}, {b[2]:+.1f} pp, {t2 / 2.75:.0f}/yr)")
    worst = res[-1]
    print(f"    (worst of the grid in-sample: {worst[1]} x{worst[0]:.2f})")
