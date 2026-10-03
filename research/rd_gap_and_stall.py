"""How a stretch above the averages resolves, and what a stalled rally does (SP-D, SP_D_HANDOFF.md section 4).

GAP: from a day stretched above its SMA20 or SMA50 inside an uptrend, the first later day
the price touches that average again: how long it took, and whether the price had to fall
to get there or the average rose to meet it.
STALL: inside an uptrend, N trading days without a new 52-week closing high; over the next
20 days: a new high (resumed), an 8% fall from the peak (ended), or neither (sideways).
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
sma = {p: talib.SMA(c, p) for p in (20, 50, 200)}
uptrend = (sma[50] > sma[200]) & np.array([x.year >= 2014 for x in d])
MAX_WAIT = 120

print("GAP -- uptrend days, 2014-2026: how the distance to the average resolved")
for p, bands in ((20, ((3, 6), (6, 9), (9, 99))), (50, ((5, 10), (10, 15), (15, 99)))):
    dist = (c / sma[p] - 1) * 100
    print(f"\n  SMA{p}")
    print("   stretch now   days  closed within 120d   median days   price at the touch vs now:"
          "   fell first   median")
    for lo, hi in bands:
        idx = [i for i in range(n - MAX_WAIT) if uptrend[i] and lo <= dist[i] < hi]
        waits, moves = [], []
        for i in idx:
            k = next((k for k in range(i + 1, i + MAX_WAIT + 1) if c[k] <= sma[p][k]), None)
            if k is not None:
                waits.append(k - i)
                moves.append((c[k] / c[i] - 1) * 100)
        if not idx:
            continue
        fell = np.mean([m < 0 for m in moves]) * 100 if moves else float("nan")
        print(f"   +{lo}..{'' if hi == 99 else '+' + str(hi)}%{'+' if hi == 99 else ' '}   {len(idx):5}    "
              f"{len(waits) / len(idx) * 100:5.0f}%              {np.median(waits) if waits else float('nan'):5.0f}          "
              f"                    {fell:5.0f}%     {np.median(moves) if moves else float('nan'):+5.1f}%")
    i = n - 1
    print(f"   today: +{dist[i]:.1f}% above SMA{p} ({sma[p][i] / 1e7:.2f} M)")

hi250 = np.array([c[max(0, i - 249):i + 1].max() for i in range(n)])
since = np.zeros(n, int)
for i in range(1, n):
    since[i] = 0 if c[i] >= hi250[i] else since[i - 1] + 1
print("\nSTALL -- uptrend days with N days since the last 52-week high; next 20 trading days")
print("   days without a new high   days   resumed (new high)   ended (8% off peak)   sideways")
for lo, hi in ((0, 1), (1, 5), (5, 10), (10, 20), (20, 40), (40, 250)):
    idx = [i for i in range(n - 20) if uptrend[i] and lo <= since[i] < hi]
    if not idx:
        continue
    res = end = 0
    for i in idx:
        peak = hi250[i]
        nxt = c[i + 1:i + 21]
        r = nxt.max() > peak
        e = (np.minimum.accumulate(nxt) <= peak * 0.92).any()
        res += r
        end += (e and not r)
    k = len(idx)
    print(f"   {lo:3}..{hi - 1:3}                    {k:5}      {res / k * 100:5.0f}%              "
          f"{end / k * 100:5.0f}%              {(k - res - end) / k * 100:5.0f}%")
print(f"   today: {since[-1]} days since the last new high ({hi250[-1] / 1e7:.2f} M)")
