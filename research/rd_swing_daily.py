"""Brave trader, daily evidence: a held CORE plus a SWING part traded on stretches and
pullbacks, against holding (SP-D, 2026-10-04).

The owner (2026-10-04): "the analyst or the system trader is a brave one, not a
conservative person": buy at 26.77, sell at 27.00, buy back at 26.50. In an economy where
18K's drift was +39%/yr (2014-2023), being out of gold is the largest cost there is, so
the design holds a core share always and trades only the rest:

  swing OUT  when the close is >= STRETCH above its EMA20 (or RSI14 >= RSI_HIGH): sell
             the swing part into the stretch;
  swing IN   when the close is back within PULLBACK of its EMA20, or after MAX_OUT days
             out (never miss a trend for long);
  core       out only on the confirmed break (v0), back on recovery.

Signals at day i's close, trade at day i+1's close, one trade a day; continuous shares
(whole-gram rounding is a separate effect). Costs: Daric 0.30%, Goldika 2.37% round trip.
In-sample 2014-2023, holdout 2024-2026; quarters (Persian) better/worse than holding.
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
rsi = talib.RSI(c, 14)
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


def run(lo, hi, cost, core, stretch, pullback, max_out, rsi_high, use_break=True):
    idx = [i for i in range(n) if lo <= d[i] <= hi and i >= 260]
    half = cost / 200
    gold, cash = 0.0, 1.0                       # grams (in units of value at the start), cash
    swing_out_since, core_out, trades = None, False, 0
    vals = []
    first = True
    for k in range(len(idx) - 1):
        i, j = idx[k], idx[k + 1]
        # core state (v0's confirmed break)
        broke = (not rally[i]) and c[i] < s50[i]
        back = (c[i] > s50[i] and e20[i] > e50[i]) or (rally[i] and not rally[i - 1])
        core_out = use_break and ((core_out or broke) and not back)
        stretched = c[i] >= e20[i] * (1 + stretch / 100) or rsi[i] >= rsi_high
        pulled = c[i] <= e20[i] * (1 + pullback / 100)
        if swing_out_since is None and stretched:
            swing_out_since = k
        elif swing_out_since is not None and (pulled or k - swing_out_since >= max_out):
            swing_out_since = None
        target = 0.0 if core_out else (core if swing_out_since is not None else 1.0)
        buy, sell = c[j] * (1 + half), c[j] * (1 - half)
        value = cash + gold * sell
        share = gold * sell / value
        if first or abs(target - share) > 0.05:
            want = target * value
            have = gold * sell
            if want > have:
                spend = min(cash, want - have)
                gold += spend / buy
                cash -= spend
            else:
                sold = (have - want) / sell
                gold -= sold
                cash += sold * sell
            trades += 1
            first = False
        vals.append((d[j], cash + gold * sell))
    return vals, trades


def summary(vals, base):
    v = vals[-1][1]
    peak, worst = 0, 0
    for _, x in vals:
        peak = max(peak, x)
        worst = min(worst, x / peak - 1)
    q, qb = quarters(vals), quarters(base)
    ex = [q[k] - qb[k] for k in q if k in qb]
    return v, worst, sum(e > 0.001 for e in ex), sum(e < -0.001 for e in ex), np.mean(ex) * 100


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


GRID = list(itertools.product((0.5, 0.7), (6, 9), (0, 2), (10, 20), (75, 101)))
for cost, venue in ((0.30, "Daric"), (2.37, "Goldika")):
    print(f"\n######## {venue} ({cost}% round trip)")
    ins_lo, ins_hi, out_lo, out_hi = date(2014, 1, 1), date(2023, 12, 31), date(2024, 1, 1), date(2027, 1, 1)
    base_in = run(ins_lo, ins_hi, cost, 1.0, 999, 0, 1, 101, use_break=False)[0]
    base_out = run(out_lo, out_hi, cost, 1.0, 999, 0, 1, 101, use_break=False)[0]
    print(f"  buy and hold: 2014-2023 x{base_in[-1][1]:.2f}   2024-2026 x{base_out[-1][1]:.2f}")
    results = []
    for core, stretch, pullback, max_out, rsi_high in GRID:
        vin, tin = run(ins_lo, ins_hi, cost, core, stretch, pullback, max_out, rsi_high)
        s_in = summary(vin, base_in)
        results.append((s_in[0], (core, stretch, pullback, max_out, rsi_high), s_in, tin))
    results.sort(key=lambda x: -x[0])
    print("  best 5 in-sample (2014-2023), then the same rule on the 2024-2026 holdout:")
    for _, params, s_in, tin in results[:5]:
        vout, tout = run(out_lo, out_hi, cost, *params)
        s_out = summary(vout, base_out)
        core, stretch, pullback, max_out, rsi_high = params
        print(f"    core {core:.0%} out at +{stretch}% over EMA20{'' if rsi_high > 100 else ' or RSI>=' + str(rsi_high)}, "
              f"back within +{pullback}% or {max_out}d | in x{s_in[0]:.2f} (q {s_in[2]}-{s_in[3]}, "
              f"{s_in[4]:+.1f} pp, {tin / 10:.0f}/yr) | holdout x{s_out[0]:.2f} (q {s_out[2]}-{s_out[3]}, "
              f"{s_out[4]:+.1f} pp, worst {s_out[1] * 100:.0f}%, {tout / 2.75:.0f}/yr)")
