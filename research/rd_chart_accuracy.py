"""How accurate is the chart? (SP-D, 2026-10-04)

The owner: "the chart itself is good, but how accurate is it? ... how can we lock the
accuracy to +95%?" A line on a chart is a claim about the future: price will respect it.
This measures that claim, on tgju's daily 18K candles (2014-2026), with every line drawn
exactly as the 21:00 chart draws it and only from the days before (causal).

Two questions for each kind of line, against a CONTROL -- the same kind of line placed at a
distance from the price taken from another day (shuffled), so it carries no information
about this day's swings. A line is worth something only by how much it beats its control.

1. PROJECTION: the chart extends each trend line 10 days ahead, dotted. Did every close of
   those 10 days stay on its side (beyond the line by no more than 0.5%)?
2. REACTION: when price first comes to the line (within 0.5%) in the next 20 days, does it
   bounce (close 3% off the line, away) before it breaks (close 2% through)?

Lines: the sloped trend lines (`trendlines`), the horizontal swing levels (`swing_levels`,
the nearest support and resistance) and, inside a rally, the Fibonacci retracements of the
rally (`rally_legs` + `fibonacci`) against the non-Fibonacci depths 15/30/44/56/70%.
"""
import json
import os
from datetime import date

import numpy as np

import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from caluclator.technical import (TRENDLINE_TOLERANCE, rally_legs, split_levels,  # noqa: E402
                                  swing_levels, trendlines)

HERE = os.path.dirname(os.path.abspath(__file__))
T = json.load(open(os.path.join(HERE, "data", "tgju_history.json")))["geram18"]
d = [date.fromisoformat(r["date"]) for r in T]
o, h, l, c = (np.array([float(r[k]) for r in T]) for k in ("open", "high", "low", "close"))
usable = ~((o == h) & (h == l) & (l == c))
# a flat candle's low and high are its close: the reaction test then reads closes
l = np.where(usable, l, c)
h = np.where(usable, h, c)
n = len(c)
FIRST = next(i for i in range(n) if d[i] >= date(2014, 1, 1))
STEP = 3            # a sample every 3 trading days
PROJECT = 10
REACH = 20
BOUNCE, BREAK = 0.03, 0.02
TOL = TRENDLINE_TOLERANCE
rng = np.random.default_rng(7)


def outcome(kind, value_at, i):
    """(projection held, reaction) for a line value_at(t), sampled on day i.
    reaction: "bounce", "break", or None when price never came to it or neither happened."""
    sign = 1 if kind == "support" else -1
    end = min(n - 1, i + PROJECT)
    held = all(sign * (c[t] - value_at(t) * (1 - sign * TOL)) >= 0 for t in range(i + 1, end + 1))
    for t in range(i + 1, min(n - 1, i + REACH) + 1):
        reached = l[t] <= value_at(t) * (1 + TOL) if sign > 0 else h[t] >= value_at(t) * (1 - TOL)
        if not reached:
            continue
        for u in range(t, min(n - 1, t + 10) + 1):
            v = value_at(u)
            if sign * (c[u] - v) <= -BREAK * v:
                return held, "break"
            if sign * (c[u] - v) >= BOUNCE * v:
                return held, "bounce"
        return held, None
    return held, None


def score(results):
    held = np.mean([r[0] for r in results]) * 100 if results else float("nan")
    reacted = [r[1] for r in results if r[1]]
    bounce = np.mean([r == "bounce" for r in reacted]) * 100 if reacted else float("nan")
    return held, bounce, len(results), len(reacted)


def report(label, real, control):
    a, b = score(real), score(control)
    se = np.sqrt(max(b[1], 1) * (100 - min(b[1], 99)) / max(1, a[3] / PROJECT * STEP))
    print(f"   {label:26} projection held {a[0]:5.1f}% (control {b[0]:5.1f}%)   "
          f"bounced {a[1]:5.1f}% of {a[3]:4} touches (control {b[1]:5.1f}%)  edge {a[1] - b[1]:+5.1f} pp (+/-{2 * se:.0f})")


# 1. sloped trend lines and horizontal swing levels
lines = {"support": [], "resistance": []}
levels = {"support": [], "resistance": []}
for i in range(FIRST, n - 1, STEP):
    tl = trendlines(h, l, c, upto=i, usable=usable)
    for kind in ("support", "resistance"):
        line = tl[kind]
        if line:
            slope = (line["y2"] - line["y1"]) / (line["i2"] - line["i1"])
            lines[kind].append((i, line["at"] / c[i] - 1, slope / c[i]))
    sup, res = split_levels(swing_levels(h, l, upto=i, usable=usable), c[i])
    for kind, lv in (("support", sup), ("resistance", res)):
        if lv:
            levels[kind].append((i, lv[0]["price"] / c[i] - 1, 0.0))


def evaluate(records, shuffle):
    dists = [r[1] for r in records]
    if shuffle:
        dists = list(rng.permutation(dists))
    return dists


print("TREND LINES AND LEVELS, 18K daily 2014-2026")
for name, table in (("trend line", lines), ("swing level", levels)):
    for kind in ("support", "resistance"):
        recs = table[kind]
        real, ctrl = [], []
        shuffled = evaluate(recs, True)
        for (i, dist, slope), dist_c in zip(recs, shuffled):
            base = c[i]
            real.append(outcome(kind, lambda t, i=i, dist=dist, slope=slope: base * (1 + dist) + slope * base * (t - i), i))
            ctrl.append(outcome(kind, lambda t, i=i, dist=dist_c, slope=slope: base * (1 + dist) + slope * base * (t - i), i))
        report(f"{name}, {kind}", real, ctrl)
        far = [abs(r[1]) for r in recs]
        print(f"   {'':26} {len(recs)} samples; the line sat {np.median(far) * 100:.1f}% from the price (median)")

# 2. Fibonacci retracements inside a rally, against non-Fibonacci depths
direction, start = rally_legs(c)
FIB = (0.236, 0.382, 0.5, 0.618)
OTHER = (0.15, 0.30, 0.44, 0.56, 0.70)
touch = {r: [] for r in FIB + OTHER}
for i in range(FIRST + 1, n - 11):
    if direction[i - 1] != "up":
        continue
    a = c[start[i - 1]]
    b = c[start[i - 1]:i].max()
    if b <= a * 1.08:
        continue
    for r in FIB + OTHER:
        lv = b - (b - a) * r
        if c[i - 1] > lv * (1 + TOL) and l[i] <= lv * (1 + TOL):
            res = None
            for u in range(i, min(n - 1, i + 10) + 1):
                if c[u] <= lv * (1 - BREAK):
                    res = "break"
                    break
                if c[u] >= lv * (1 + BOUNCE):
                    res = "bounce"
                    break
            if res:
                touch[r].append(res == "bounce")

print("\nFIBONACCI, inside a rally (8% ZigZag), first touch from above: bounced 3% before breaking 2%")
for group, ratios in (("Fibonacci", FIB), ("other depths", OTHER)):
    for r in ratios:
        v = touch[r]
        print(f"   {group:13} {r * 100:5.1f}%: {np.mean(v) * 100:5.1f}% of {len(v)} touches")
fib_all = [x for r in FIB for x in touch[r]]
oth_all = [x for r in OTHER for x in touch[r]]
print(f"   ALL Fibonacci {np.mean(fib_all) * 100:.1f}% of {len(fib_all)}  |  ALL other {np.mean(oth_all) * 100:.1f}% of {len(oth_all)}")

# 3. what "accuracy" measures: a horizontal line with no history, at a fixed distance
print("\nA LINE WITH NO HISTORY, drawn at a fixed distance: share of 10-day projections that held")
for kind in ("support", "resistance"):
    sign = -1 if kind == "support" else 1
    cells = []
    for dist in (0.01, 0.02, 0.03, 0.05, 0.08, 0.10, 0.15):
        held = [outcome(kind, lambda t, v=c[i] * (1 + sign * dist): v, i)[0] for i in range(FIRST, n - PROJECT - 1, STEP)]
        cells.append(f"{dist * 100:.0f}% away {np.mean(held) * 100:.0f}%")
    print(f"   {kind:10} " + ", ".join(cells))
