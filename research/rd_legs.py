"""Trend legs: the long uptrend broken into rallies and corrections (SP-D research, section 49).

A ZigZag over daily closes: a rally ends when the price falls REVERSAL_PCT from its peak,
a correction ends when it rises REVERSAL_PCT from its trough. The last swing is still
open: its end is not known, and it is reported as the current leg, not as a finished one.
"""
import json
import os
from datetime import date
from statistics import median

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = json.load(open(os.path.join(HERE, "data", "tgju_history.json")))
rows = DATA["geram18"]
d = [date.fromisoformat(r["date"]) for r in rows]
c = [float(r["close"]) for r in rows]
n = len(c)


def zigzag(threshold):
    """[(kind, start_index, end_index)] with kind 'rally' or 'correction'; last is open."""
    pivots = [0]
    direction = None
    extreme = 0
    for i in range(1, n):
        if direction in (None, "up"):
            if c[i] > c[extreme]:
                extreme = i
            elif c[i] <= c[extreme] * (1 - threshold):
                if direction is None and extreme == 0:
                    direction = "down"; extreme = i; continue
                pivots.append(extreme); direction = "down"; extreme = i
        if direction == "down":
            if c[i] < c[extreme]:
                extreme = i
            elif c[i] >= c[extreme] * (1 + threshold):
                pivots.append(extreme); direction = "up"; extreme = i
        if direction is None and c[i] >= c[0] * (1 + threshold):
            direction = "up"
    pivots.append(extreme)
    legs = []
    for a, b in zip(pivots, pivots[1:]):
        if b > a:
            legs.append(("rally" if c[b] > c[a] else "correction", a, b))
    return legs


for threshold in (0.05, 0.08):
    legs = zigzag(threshold)
    done = legs[:-1]
    rallies = [(b - a, (c[b] / c[a] - 1) * 100) for k, a, b in done if k == "rally" and d[a].year >= 2014]
    corrs = [(b - a, (c[b] / c[a] - 1) * 100) for k, a, b in done if k == "correction" and d[a].year >= 2014]
    print(f"\n==== reversal {threshold:.0%}: {len(rallies)} rallies and {len(corrs)} corrections since 2014")
    print(f"  rallies:     median {median(x[0] for x in rallies):.0f} trading days, median gain {median(x[1] for x in rallies):+.1f}%"
          f"; longest {max(x[0] for x in rallies)} days; largest {max(x[1] for x in rallies):+.0f}%")
    print(f"  corrections: median {median(x[0] for x in corrs):.0f} trading days, median depth {median(x[1] for x in corrs):+.1f}%"
          f"; deepest {min(x[1] for x in corrs):+.0f}%")
    k, a, b = legs[-1]
    age, move = n - 1 - a, (c[-1] / c[a] - 1) * 100
    rank_age = sum(1 for x in rallies if x[0] < age) / len(rallies) * 100
    rank_gain = sum(1 for x in rallies if x[1] < move) / len(rallies) * 100
    print(f"  CURRENT {k} since {d[a]} ({c[a] / 1e7:.2f} M): {age} trading days, {move:+.1f}% "
          f"-- longer than {rank_age:.0f}% and larger than {rank_gain:.0f}% of past rallies")
    print("  legs since the major uptrend began (2023-11-29):")
    for kind, a, b in legs:
        if d[b] >= date(2023, 11, 29):
            end = "open" if (kind, a, b) == legs[-1] else f"{d[b]}"
            print(f"    {kind:10} {d[a]} -> {end:10}  {b - a:4} days  {(c[b] / c[a] - 1) * 100:+6.1f}%   "
                  f"{c[a] / 1e7:5.2f} M -> {c[b] / 1e7:5.2f} M")
