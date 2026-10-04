"""Paper portfolio v0: candidate analyst policies under the owner's contract (SP-D).

Contract (owner, 2026-10-04): 100,000,000 toman; whole grams only (residue stays as cash);
at most one trade per day; no borrowing, no short selling; one venue, buying at its buy
price and selling at its sell price; judged per Persian quarter on value in toman.

Each policy sets a TARGET share of the portfolio in gold from what the R&D tested (the
analyst rulebook, the 8% rally state, the 50-day average, the dollar's trend). A trade is
made only when the target and the current share differ by at least BAND, and then moves
all the way to the target, in whole grams. Signals use day i's close; the trade executes
at day i+1's close (no look-ahead). Venue costs: Goldika's buy/sell quotes were 2.37%
apart, Daric's order book 0.26-0.30% (2026-10-04).

Scored against buying on day one and holding, per period and per Persian quarter, with
the 2026-01-29 -> 2026-06-16 drop (-24%) looked at on its own.
"""
import json
import math
import os
import sys
from datetime import date

import numpy as np
import talib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
from timeutil import persian_quarter

D = json.load(open(os.path.join(HERE, "data", "tgju_history.json")))
rows = D["geram18"]
d = [date.fromisoformat(r["date"]) for r in rows]
c = np.array([float(r["close"]) for r in rows]) / 10          # toman per gram
n = len(c)
s50, s200 = talib.SMA(c, 50), talib.SMA(c, 200)
e20, e50 = talib.EMA(c, 20), talib.EMA(c, 50)
hi250 = np.array([c[max(0, i - 249):i + 1].max() for i in range(n)])
since = np.zeros(n, int)
for i in range(1, n):
    since[i] = 0 if c[i] >= hi250[i] else since[i - 1] + 1
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
ud = [date.fromisoformat(r["date"]) for r in D["price_dollar_rl"]]
uc = np.array([float(r["close"]) for r in D["price_dollar_rl"]])
u50 = talib.SMA(uc, 50)
from bisect import bisect_right
uidx = [bisect_right(ud, x) - 1 for x in d]
usd_up = np.array([j >= 0 and not np.isnan(u50[j]) and uc[j] > u50[j] for j in uidx])


def score(i):
    s = 0
    if c[i] > s50[i] > s200[i] and s50[i] > s50[i - 10]:
        s += 1
    if c[i] < s50[i]:
        s -= 1
    if since[i] <= 4:
        s += 1
    if since[i] >= 20:
        s -= 1
    s += 1 if usd_up[i] else -1
    if not rally[i]:
        s -= 1
    return s


def label(s):
    return "SB" if s >= 3 else "B" if s == 2 else "N" if s >= 0 else "BE" if s >= -2 else "SBE"


exit_state = {}


def p_break(i, with_usd=False):
    """Fully invested; out only on a confirmed break: rally broken AND below the 50-day
    (AND, with_usd, the dollar below its 50-day). Back in when the price is above the
    50-day again with EMA20 above EMA50, or a new rally starts."""
    key = ("brk", with_usd)
    out = exit_state.get(key, False)
    broke = (not rally[i]) and c[i] < s50[i] and (not with_usd or not usd_up[i])
    back = (c[i] > s50[i] and e20[i] > e50[i]) or (rally[i] and not rally[i - 1])
    out = (out or broke) and not back
    exit_state[key] = out
    return 0.0 if out else 1.0


POLICIES = {
    "buy and hold": lambda i: 1.0,
    "stance 1/1/.5/0/0": lambda i: {"SB": 1, "B": 1, "N": 0.5, "BE": 0, "SBE": 0}[label(score(i))],
    "stance 1/1/.75/.25/0": lambda i: {"SB": 1, "B": 1, "N": 0.75, "BE": 0.25, "SBE": 0}[label(score(i))],
    "out on a confirmed break": lambda i: p_break(i),
    "break + dollar below 50d": lambda i: p_break(i, with_usd=True),
}
BAND = 0.2
START = 100_000_000


def simulate(policy, lo, hi, spread_pct):
    exit_state.clear()
    idx = [i for i in range(n) if lo <= d[i] <= hi and not np.isnan(s200[i]) and i >= 260]
    half = spread_pct / 200
    cash, grams, trades = float(START), 0, 0
    values, peak, worst = [], START, 0.0
    for k in range(len(idx) - 1):
        i, j = idx[k], idx[k + 1]
        target = policy(i)
        buy, sell = c[j] * (1 + half), c[j] * (1 - half)
        value = cash + grams * sell
        share = grams * sell / value if value else 0
        if abs(target - share) >= BAND:
            want = int(math.floor(target * value / buy)) if target > share else int(math.floor(target * value / sell))
            if want > grams:
                g = min(want - grams, int(cash // buy))
                if g >= 1:
                    grams, cash, trades = grams + g, cash - g * buy, trades + 1
            elif want < grams:
                g = grams - want
                grams, cash, trades = want, cash + g * sell, trades + 1
        value = cash + grams * sell
        values.append((d[j], value))
        peak = max(peak, value)
        worst = min(worst, value / peak - 1)
    return values, worst, trades


def by_quarter(values):
    out, base, cur = {}, START, None
    for day, v in values:
        q = persian_quarter(day)[2]
        if q != cur:
            if cur is not None:
                out[cur] = (base, last)
            base, cur = (last if cur is not None else START), q
        last = v
    out[cur] = (base, last)
    return {q: e / b - 1 for q, (b, e) in out.items()}


for spread, venue in ((2.37, "Goldika"), (0.30, "Daric")):
    print(f"\n######## venue {venue}: round trip {spread}%")
    for lo, hi in ((date(2014, 1, 1), date(2023, 12, 31)), (date(2024, 1, 1), date(2027, 1, 1))):
        print(f"\n  {lo.year}-{min(hi.year, 2026)}")
        base_q = by_quarter(simulate(POLICIES["buy and hold"], lo, hi, spread)[0])
        for name, policy in POLICIES.items():
            values, worst, trades = simulate(policy, lo, hi, spread)
            q = by_quarter(values)
            excess = [q[k] - base_q[k] for k in q if k in base_q]
            wins = sum(e > 0.001 for e in excess)
            loses = sum(e < -0.001 for e in excess)
            print(f"    {name:26} x{values[-1][1] / START:6.2f}  worst {worst * 100:6.1f}%  trades {trades:3}  "
                  f"quarters vs hold: better {wins:2} worse {loses:2} of {len(excess)}  mean {np.mean(excess) * 100:+5.1f} pp")

    print("\n  2026-01-29 -> 2026-06-16 (18K -24.1%) and on to 2026-10-01")
    for name, policy in POLICIES.items():
        values, worst, trades = simulate(policy, date(2025, 10, 1), date(2027, 1, 1), spread)
        v = dict(values)
        a, b, e = v.get(date(2026, 1, 29)), v.get(date(2026, 6, 16)), values[-1][1]
        print(f"    {name:26} drop {(b / a - 1) * 100:+6.1f}%   then to 10-01 {(e / b - 1) * 100:+6.1f}%   "
              f"whole span {(e / a - 1) * 100:+6.1f}%   trades {trades}")
