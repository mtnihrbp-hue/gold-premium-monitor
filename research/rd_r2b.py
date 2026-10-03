"""R2b -- trading-principle pieces that can be made objective (SP-D research, SP_D_HANDOFF.md section 4).

1. LEVELS against a baseline. A support "holds" if, within 20 trading days, 18K never
   closes 2% or more below it. A level 0-2% below the price holds fairly often by chance,
   so every level type is compared with a level at the SAME distance below the price
   that has no history behind it. Types: swing lows (SP_D_HANDOFF.md section 1.1) and time-at-price
   zones (the Volume Profile proxy: where 18K's daily closes clustered over a year).
2. FAILED BREAKOUT (a liquidity-sweep proxy): a new 52-week closing high that closes back
   below the prior high within 3 days.
3. FAIR VALUE GAPS: three-candle gaps on tgju's daily candles (real ranges only); the
   20-day move after them, and how often price came back into the gap.
All causal; in-sample 2014-2023, holdout 2024-2026.
"""
import json
import os
from datetime import date

import numpy as np

import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from caluclator.technical import split_levels, swing_levels

HERE = os.path.dirname(os.path.abspath(__file__))
rows = json.load(open(os.path.join(HERE, "data", "tgju_history.json")))["geram18"]
d = [date.fromisoformat(r["date"]) for r in rows]
o, h, l, c = (np.array([float(r[k]) for r in rows]) for k in ("open", "high", "low", "close"))
n = len(c)
flat = (o == h) & (h == l) & (l == c)
bad = (l > np.minimum(o, c)) | (h < np.maximum(o, c))
real = ~(flat | bad)
H = 20
fwd = np.full(n, np.nan); fwd[:n - H] = (c[H:] / c[:n - H] - 1) * 100
period = lambda i: "in" if date(2014, 1, 1) <= d[i] <= date(2023, 12, 31) else ("hold" if d[i] >= date(2024, 1, 1) else None)


def holds(i, level):
    """No close 2%+ below `level` within the next H days."""
    return bool((c[i + 1:i + H + 1] > level * 0.98).all())


def profile_zones(i, lookback=250, bin_pct=1.0, top=5):
    """Time-at-price: the most-visited 1% price bins of the last `lookback` closes."""
    window = c[max(0, i - lookback + 1):i + 1]
    edges = np.exp(np.arange(np.log(window.min()), np.log(window.max()) + bin_pct / 100, bin_pct / 100))
    if len(edges) < 3:
        return []
    counts, _ = np.histogram(window, bins=edges)
    order = np.argsort(counts)[::-1][:top]
    return [float((edges[k] + edges[k + 1]) / 2) for k in order if counts[k] > 0]


print("1. SUPPORTS against a no-history level at the same distance (price within 2% above)")
res = {"swing": {"in": [], "hold": []}, "profile": {"in": [], "hold": []}}
for i in range(300, n - H):
    p = period(i)
    if p is None:
        continue
    sup, _ = split_levels(swing_levels(h, l, upto=i, usable=real), c[i])
    if sup and 0 <= (c[i] / sup[0]["price"] - 1) * 100 <= 2:
        res["swing"][p].append(holds(i, sup[0]["price"]))
    below = [z for z in profile_zones(i) if z < c[i] and (c[i] / z - 1) * 100 <= 2]
    if below:
        res["profile"][p].append(holds(i, max(below)))
# the baseline: any level at 0-2% below the price, without history -- the same test on a
# synthetic level at each day's own distance (drawn uniformly in 0-2%)
rng = np.random.default_rng(7)
base = {"in": [], "hold": []}
for i in range(300, n - H):
    p = period(i)
    if p is not None:
        base[p].append(holds(i, c[i] / (1 + rng.uniform(0, 0.02))))
for name in ("swing", "profile"):
    for p in ("in", "hold"):
        v, b = res[name][p], base[p]
        print(f"   {name:8} {p:4}: {len(v):4} days, held {np.mean(v) * 100:4.0f}%   no-history level: {np.mean(b) * 100:4.0f}%"
              f"   edge {np.mean(v) * 100 - np.mean(b) * 100:+4.0f} pp")

print("\n2. FAILED BREAKOUT: a new 52-week high that closes back below the prior high within 3 days")
prior = np.array([c[max(0, i - 250):i].max() if i > 0 else np.nan for i in range(n)])
events = {"in": [], "hold": []}
for i in range(251, n - H - 3):
    if c[i] > prior[i] and c[i - 1] <= prior[i - 1]:
        k = next((k for k in range(i + 1, i + 4) if c[k] < prior[i]), None)
        if k is not None and period(k):
            events[period(k)].append(k)
for p in ("in", "hold"):
    idx = events[p]
    pool = [i for i in range(300, n - H) if period(i) == p]
    if idx:
        print(f"   {p:4}: {len(idx):3} events; 20d move median {np.median(fwd[idx]):+5.1f}% vs all days {np.median(fwd[pool]):+5.1f}%; "
              f"higher {np.mean(fwd[idx] > 0) * 100:3.0f}% vs {np.mean(fwd[pool] > 0) * 100:3.0f}%")

print("\n3. FAIR VALUE GAPS (three real candles)")
for kind in ("bullish", "bearish"):
    for p in ("in", "hold"):
        idx, filled, days = [], 0, []
        for i in range(2, n - H):
            if not (real[i] and real[i - 1] and real[i - 2]) or period(i) != p:
                continue
            if kind == "bullish" and l[i] > h[i - 2]:
                top, bottom = l[i], h[i - 2]
            elif kind == "bearish" and h[i] < l[i - 2]:
                top, bottom = l[i - 2], h[i]
            else:
                continue
            idx.append(i)
            k = next((k for k in range(i + 1, i + H + 1) if (l[k] <= top if kind == "bullish" else h[k] >= bottom)), None)
            if k is not None:
                filled += 1; days.append(k - i)
        pool = [i for i in range(300, n - H) if period(i) == p]
        if idx:
            print(f"   {kind:7} {p:4}: {len(idx):4} gaps; back into the gap within 20d {filled / len(idx) * 100:3.0f}% "
                  f"(median {np.median(days) if days else float('nan'):.0f} days); 20d move median {np.median(fwd[idx]):+5.1f}% "
                  f"vs all {np.median(fwd[pool]):+5.1f}%; higher {np.mean(fwd[idx] > 0) * 100:3.0f}% vs {np.mean(fwd[pool] > 0) * 100:3.0f}%")
