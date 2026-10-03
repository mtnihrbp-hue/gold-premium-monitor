"""The analyst stance: a fixed rulebook from the signals that passed, then tested itself.

Score (each causal): trend up +1 / price below its 50-day -1; a new 52-week high in the last
4 days +1 / none for 20+ days -1; the dollar above its 50-day +1 / below -1; the rally broken
(8% off its peak) -1. Stance: score >= 3 STRONG BULLISH, 2 BULLISH, 0..1 NEUTRAL, -1..-2
BEARISH, <= -3 STRONG BEARISH. Qualifier STRETCHED when 9%+ above the 20-day average.
Nothing is fitted: if the stances do not separate what followed, the stance is decoration.
"""
import json
import os
from bisect import bisect_right
from datetime import date

import numpy as np
import talib

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = json.load(open(os.path.join(HERE, "data", "tgju_history.json")))


def series(inst):
    rows = DATA[inst]
    return [date.fromisoformat(r["date"]) for r in rows], np.array([float(r["close"]) for r in rows])


gd, c = series("geram18")
ud, uc = series("price_dollar_rl")
n = len(c)
s20, s50, s200 = talib.SMA(c, 20), talib.SMA(c, 50), talib.SMA(c, 200)
u50 = talib.SMA(uc, 50)
uidx = [bisect_right(ud, x) - 1 for x in gd]
usd_above = np.array([uc[j] > u50[j] if j >= 0 and not np.isnan(u50[j]) else np.nan for j in uidx], dtype=float)
hi250 = np.array([c[max(0, i - 249):i + 1].max() for i in range(n)])
since = np.zeros(n, int)
for i in range(1, n):
    since[i] = 0 if c[i] >= hi250[i] else since[i - 1] + 1
# rally peak: highest close since the last 8% ZigZag trough confirmed by day i
peak = np.zeros(n); trough_i = 0; state = "up"; ext = 0
for i in range(n):
    if state == "up":
        if c[i] > c[ext]: ext = i
        elif c[i] <= c[ext] * 0.92: state, ext = "down", i
    else:
        if c[i] < c[ext]: ext = i
        elif c[i] >= c[ext] * 1.08: state, trough_i, ext = "up", ext, i
    peak[i] = c[trough_i:i + 1].max()
broken = c <= peak * 0.92


def score(i):
    s = 0
    if c[i] > s50[i] > s200[i] and s50[i] > s50[i - 10]: s += 1
    if c[i] < s50[i]: s -= 1
    if since[i] <= 4: s += 1
    if since[i] >= 20: s -= 1
    if usd_above[i] == 1: s += 1
    elif usd_above[i] == 0: s -= 1
    if broken[i]: s -= 1
    return s


def stance(s):
    return ("STRONG BULLISH" if s >= 3 else "BULLISH" if s == 2 else "NEUTRAL" if s >= 0
            else "BEARISH" if s >= -2 else "STRONG BEARISH")


fwd = np.full(n, np.nan); fwd[:n - 20] = (c[20:] / c[:n - 20] - 1) * 100
fwd60 = np.full(n, np.nan); fwd60[:n - 60] = (c[60:] / c[:n - 60] - 1) * 100
fell5 = np.full(n, np.nan)
for i in range(n - 20):
    fell5[i] = float(c[i + 1:i + 21].min() / c[i] - 1 <= -0.05)
valid = [i for i in range(220, n - 20) if not np.isnan(s200[i]) and not np.isnan(usd_above[i])]
labels = ["STRONG BULLISH", "BULLISH", "NEUTRAL", "BEARISH", "STRONG BEARISH"]
for name, lo, hi in (("2014-2023", date(2014, 1, 1), date(2023, 12, 31)), ("2024-2026 held back", date(2024, 1, 1), date(2027, 1, 1))):
    sel = [i for i in valid if lo <= gd[i] <= hi]
    print(f"\n{name}: {len(sel)} days; all days: higher after 20d {np.mean(fwd[sel] > 0) * 100:.0f}%, "
          f"median {np.median(fwd[sel]):+.1f}%, fell 5%+ on the way {np.nanmean(fell5[sel]) * 100:.0f}%")
    print("   stance            days   higher 20d   median 20d   median 60d   fell 5%+ within 20d")
    for lab in labels:
        idx = [i for i in sel if stance(score(i)) == lab]
        if not idx:
            continue
        f60 = fwd60[idx]; f60 = f60[~np.isnan(f60)]
        print(f"   {lab:16} {len(idx):5}      {np.mean(fwd[idx] > 0) * 100:3.0f}%       {np.median(fwd[idx]):+5.1f}%      "
              f"{np.median(f60) if len(f60) else float('nan'):+5.1f}%          {np.nanmean(fell5[idx]) * 100:3.0f}%")
    st = [i for i in sel if (c[i] / s20[i] - 1) * 100 >= 9]
    print(f"   STRETCHED (9%+ over SMA20) {len(st)} days: higher 20d {np.mean(fwd[st] > 0) * 100:.0f}%, "
          f"median {np.median(fwd[st]):+.1f}%, fell 5%+ {np.nanmean(fell5[st]) * 100:.0f}%")
i = n - 1
print(f"\nTODAY ({gd[i]}): score {score(i)} -> {stance(score(i))}; vs SMA20 {(c[i] / s20[i] - 1) * 100:+.1f}%; "
      f"days since high {since[i]}; dollar above its 50-day {bool(usd_above[i])}; rally peak {peak[i] / 1e7:.2f} M")
