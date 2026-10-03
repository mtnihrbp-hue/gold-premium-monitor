"""Decision anchors for 18K today, each with where it sits in its own history (research)."""
import json
import os
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
DATA = json.load(open(os.path.join(HERE, "data", "tgju_history.json")))
from bisect import bisect_left

import numpy as np
import talib


rows = [(date.fromisoformat(r["date"]), r["high"], r["low"], r["close"]) for r in DATA["geram18"]]
dates = [r[0] for r in rows]
H = np.array([float(r[1]) for r in rows]); L = np.array([float(r[2]) for r in rows]); C = np.array([float(r[3]) for r in rows])
n = len(C); i = n - 1
M = 1e7

sma = {p: talib.SMA(C, p) for p in (20, 50, 200)}
ema = {p: talib.EMA(C, p) for p in (20, 50)}
rsi = talib.RSI(C, 14)
macd, signal, hist = talib.MACD(C, 12, 26, 9)
adx = talib.ADX(H, L, C, 14); pdi = talib.PLUS_DI(H, L, C, 14); mdi = talib.MINUS_DI(H, L, C, 14)
atr = talib.ATR(H, L, C, 14)
upper, mid, lower = talib.BBANDS(C, 20, 2, 2)
roc20, roc60 = talib.ROC(C, 20), talib.ROC(C, 60)
uptrend = (sma[50] > sma[200])


def pct_rank(series, value, mask=None):
    vals = np.sort(series[(~np.isnan(series)) & (mask if mask is not None else True)][:-1])
    return bisect_left(vals, value) / len(vals) * 100 if len(vals) else float("nan")


print(f"18K tgju close {dates[i]}: {C[i] / M:.2f} M toman\n")
print("1. DISTANCE FROM THE AVERAGES            now      rank among uptrend days   among all days")
for name, s in (("SMA 20", sma[20]), ("EMA 20", ema[20]), ("SMA 50", sma[50]), ("EMA 50", ema[50]), ("SMA 200", sma[200])):
    dist = (C / s - 1) * 100
    print(f"   price vs {name:8} {s[i] / M:6.2f} M   {dist[i]:+6.1f}%   {pct_rank(dist, dist[i], uptrend):5.0f}th pct              {pct_rank(dist, dist[i]):5.0f}th pct")
gap = (sma[50] / sma[200] - 1) * 100
print(f"   SMA50 vs SMA200 spread               {gap[i]:+6.1f}%   {pct_rank(gap, gap[i], uptrend):5.0f}th pct")

# where in the uptrend: since SMA50 crossed above SMA200
start = i
while start > 0 and uptrend[start - 1]:
    start -= 1
age = i - start
gain = (C[i] / C[start] - 1) * 100
low_since = C[start:i + 1].min()
# completed historical uptrends: age and total gain to their peak
spans, j = [], 200
while j < i:
    if uptrend[j] and not uptrend[j - 1]:
        k = j
        while k < i and uptrend[k]:
            k += 1
        if k < i:                                    # completed
            peak = C[j:k + 1].max()
            spans.append((k - j, (peak / C[j] - 1) * 100, dates[j], dates[k]))
        j = k
    j += 1
ages = sorted(s[0] for s in spans); gains = sorted(s[1] for s in spans)
print(f"\n2. WHERE IN THE UPTREND (SMA50 above SMA200 since {dates[start]})")
print(f"   age {age} trading days; gain since it began {gain:+.1f}%; drawdown from peak {(C[i] / C[start:i + 1].max() - 1) * 100:+.1f}%")
print(f"   completed uptrends since 2014: {len(spans)}; median length {np.median(ages):.0f} days, median gain to peak {np.median(gains):+.0f}%")
print(f"   this one is longer than {bisect_left(ages, age) / len(ages) * 100:.0f}% of them and has gained more than {bisect_left(gains, gain) / len(gains) * 100:.0f}%")
print(f"   the five longest: " + "; ".join(f"{s[2]}..{s[3]} {s[0]}d {s[1]:+.0f}%" for s in sorted(spans, key=lambda s: -s[0])[:5]))


def last_cross(a, b, up=True):
    for k in range(i, 0, -1):
        if up and a[k] > b[k] and a[k - 1] <= b[k - 1]:
            return k
        if not up and a[k] < b[k] and a[k - 1] >= b[k - 1]:
            return k
    return None


print("\n3. LAST CROSSES")
for label, a, b in (("price above SMA 20", C, sma[20]), ("price above SMA 50", C, sma[50]),
                    ("SMA 20 above SMA 50", sma[20], sma[50]), ("SMA 50 above SMA 200 (golden)", sma[50], sma[200]),
                    ("MACD above its signal", macd, signal)):
    up, down = last_cross(a, b, True), last_cross(a, b, False)
    latest = max(x for x in (up, down) if x is not None)
    kind = "up" if latest == up else "down"
    print(f"   {label:32} last cross {kind:4} {dates[latest]} ({i - latest} days ago)")
k70 = next((k for k in range(i, 0, -1) if rsi[k] > 70 and rsi[k - 1] <= 70), None)
print(f"   {'RSI crossed above 70':32} {dates[k70]} ({i - k70} days ago)")

print("\n4. MOMENTUM AND STRENGTH                 now      rank among all days")
for label, s in (("RSI 14", rsi), ("MACD histogram (% of price)", hist / C * 100), ("ADX 14 (trend strength)", adx),
                 ("+DI minus -DI", pdi - mdi), ("ROC 20 days %", roc20), ("ROC 60 days %", roc60)):
    print(f"   {label:30} {s[i]:7.1f}   {pct_rank(s, s[i]):5.0f}th pct")
print("\n5. TYPICAL MOVE SIZE")
print(f"   ATR 14: {atr[i] / M:.2f} M a day = {atr[i] / C[i] * 100:.1f}% of price ({pct_rank(atr / C, atr[i] / C[i]):.0f}th pct)")
print(f"   Bollinger 20/2: band {lower[i] / M:.2f} .. {upper[i] / M:.2f} M; price at {(C[i] - lower[i]) / (upper[i] - lower[i]) * 100:.0f}% of the band")

f20 = (np.roll(C, -20) / C - 1) * 100
valid = np.arange(n) < n - 20
print("\n6. HOW MUCH, OVER THE NEXT 20 TRADING DAYS (history 2014-2026, NOT YET VALIDATED)")
for label, mask in (("all days", valid & (np.arange(n) >= 200)), ("uptrend days", valid & uptrend),
                    ("uptrend, 15%+ above SMA50", valid & uptrend & ((C / sma[50] - 1) * 100 >= 15))):
    q = np.percentile(f20[mask], [10, 25, 50, 75, 90])
    print(f"   {label:26} n={mask.sum():4}  10%: {q[0]:+5.1f}  25%: {q[1]:+5.1f}  median: {q[2]:+5.1f}  75%: {q[3]:+5.1f}  90%: {q[4]:+5.1f}")
