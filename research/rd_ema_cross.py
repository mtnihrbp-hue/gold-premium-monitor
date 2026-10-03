"""EMA 20/50 cross on 18K: state and fresh crosses, against the base rate (SP-D research).

State: EMA20 above or below EMA50 on a day. Fresh cross: the first 5 days after EMA20
crosses EMA50. Next 20 and 60 trading days: higher, median move, and (for the bullish
state) whether a 5% dip came on the way. In-sample 2014-2023, holdout 2024-2026.
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
e20, e50 = talib.EMA(c, 20), talib.EMA(c, 50)
above = e20 > e50
cross = np.zeros(n, int)                      # +1 golden, -1 death, on the day it happens
for i in range(51, n):
    if above[i] and not above[i - 1]:
        cross[i] = 1
    elif not above[i] and above[i - 1]:
        cross[i] = -1
since = np.full(n, 9999)
last = None
for i in range(n):
    if cross[i] != 0:
        last = i
    if last is not None:
        since[i] = i - last


def fwd(h):
    out = np.full(n, np.nan)
    out[:n - h] = (c[h:] / c[:n - h] - 1) * 100
    return out


f20, f60 = fwd(20), fwd(60)
dip5 = np.full(n, np.nan)
for i in range(n - 20):
    dip5[i] = float(c[i + 1:i + 21].min() / c[i] - 1 <= -0.05)
period = lambda i: "2014-23" if date(2014, 1, 1) <= d[i] <= date(2023, 12, 31) else ("2024-26" if d[i] >= date(2024, 1, 1) else None)


def line(name, idx):
    if not idx:
        return
    a = f60[idx]; a = a[~np.isnan(a)]
    print(f"   {name:34} {len(idx):5}   higher20 {np.mean(f20[idx] > 0) * 100:3.0f}%  med20 {np.median(f20[idx]):+5.1f}%"
          f"   higher60 {np.mean(a > 0) * 100 if len(a) else float('nan'):3.0f}%  med60 {np.median(a) if len(a) else float('nan'):+5.1f}%"
          f"   5% dip in 20d {np.nanmean(dip5[idx]) * 100:3.0f}%")


for p in ("2014-23", "2024-26"):
    pool = [i for i in range(60, n - 20) if period(i) == p]
    print(f"\n{p}")
    line("all days", pool)
    line("EMA20 above EMA50", [i for i in pool if above[i]])
    line("EMA20 below EMA50", [i for i in pool if not above[i]])
    line("fresh golden cross (0-4 days)", [i for i in pool if above[i] and since[i] <= 4])
    line("fresh death cross (0-4 days)", [i for i in pool if not above[i] and since[i] <= 4])
    line("golden cross held 60+ days", [i for i in pool if above[i] and since[i] >= 60])
gc = [i for i in range(60, n) if cross[i] == 1 and d[i].year >= 2014]
dc = [i for i in range(60, n) if cross[i] == -1 and d[i].year >= 2014]
print(f"\ncrosses since 2014: {len(gc)} golden, {len(dc)} death; whipsaws (reversed within 10 days): "
      f"{sum(1 for i in gc + dc if any(cross[k] for k in range(i + 1, min(n, i + 11))))}")
i = n - 1
k = max(j for j in range(n) if cross[j] != 0)
print(f"today {d[i]}: EMA20 {'above' if above[i] else 'below'} EMA50 since {d[k]} ({since[i]} days); "
      f"gap {(e20[i] / e50[i] - 1) * 100:+.1f}%; EMA20 {e20[i] / 1e7:.2f} M, EMA50 {e50[i] / 1e7:.2f} M")
