"""R2 -- event studies for 18K (tgju daily). Research only.

For each event type: what 18K did 5/20/60 trading days later and whether a 5% pullback
came within 20, against the base rate of the same period. Significance by bootstrap of
random days from the same pool; multiple testing by Benjamini-Hochberg; confirmation on
held-back years.

In-sample 2014-2023, holdout 2024-2026. Candle patterns only on days whose own candle
and the three before it carry a real range (tgju's 2019-2023 candles are often flat).
"""
import json
import random
from bisect import bisect_left
from datetime import date

import numpy as np
import talib

random.seed(7)
import os
HERE = os.path.dirname(os.path.abspath(__file__))
data = json.load(open(os.path.join(HERE, "data", "tgju_history.json")))
HORIZONS = (5, 20, 60)
PRIMARY = 20
IN_SAMPLE = (date(2014, 1, 1), date(2023, 12, 31))
HOLDOUT = (date(2024, 1, 1), date(2026, 12, 31))
BOOT = 2000


def arrays(inst):
    rows = data[inst]
    d = [date.fromisoformat(r["date"]) for r in rows]
    o, h, l, c = (np.array([float(r[k]) for r in rows]) for k in ("open", "high", "low", "close"))
    return d, o, h, l, c


gd, go, gh, gl, gc = arrays("geram18")
n = len(gc)
flat = (go == gh) & (gh == gl) & (gl == gc)
bad = (gl > np.minimum(go, gc)) | (gh < np.maximum(go, gc))
real = ~(flat | bad)
real4 = real & np.roll(real, 1) & np.roll(real, 2) & np.roll(real, 3)

fwd = {h: np.full(n, np.nan) for h in HORIZONS}
for h in HORIZONS:
    fwd[h][:n - h] = (gc[h:] / gc[:n - h] - 1) * 100
pull = np.full(n, np.nan)
for i in range(n - 20):
    pull[i] = float(gc[i + 1:i + 21].min() / gc[i] - 1 <= -0.05)


def crosses(a, b):
    up = np.zeros(len(a), bool); down = np.zeros(len(a), bool)
    ok = ~(np.isnan(a) | np.isnan(b))
    up[1:] = ok[1:] & ok[:-1] & (a[1:] > b[1:]) & (a[:-1] <= b[:-1])
    down[1:] = ok[1:] & ok[:-1] & (a[1:] < b[1:]) & (a[:-1] >= b[:-1])
    return up, down


def level_cross(x, level):
    return crosses(x, np.full(len(x), level))


def series_events(d, o, h, l, c, prefix):
    sma = {p: talib.SMA(c, p) for p in (20, 50, 200)}
    ema = {p: talib.EMA(c, p) for p in (20, 50)}
    macd, sig, _ = talib.MACD(c, 12, 26, 9)
    rsi = talib.RSI(c, 14)
    up_b, _, lo_b = talib.BBANDS(c, 20, 2, 2)
    ev = {}
    for name, (a, b) in {"price x SMA20": (c, sma[20]), "price x SMA50": (c, sma[50]),
                         "price x SMA200": (c, sma[200]), "SMA20 x SMA50": (sma[20], sma[50]),
                         "SMA50 x SMA200": (sma[50], sma[200]), "EMA20 x EMA50": (ema[20], ema[50]),
                         "MACD x signal": (macd, sig), "close x upper Bollinger": (c, up_b),
                         "close x lower Bollinger": (c, lo_b)}.items():
        u, dn = crosses(a, b)
        ev[f"{prefix}{name} up"], ev[f"{prefix}{name} down"] = u, dn
    for lvl in (70, 30):
        u, dn = level_cross(rsi, lvl)
        ev[f"{prefix}RSI crosses above {lvl}"], ev[f"{prefix}RSI crosses below {lvl}"] = u, dn
    hi = np.zeros(len(c), bool); lo = np.zeros(len(c), bool)
    for i in range(250, len(c)):
        hi[i] = c[i] > c[i - 250:i].max() and c[i - 1] <= c[i - 251:i - 1].max()
        lo[i] = c[i] < c[i - 250:i].min() and c[i - 1] >= c[i - 251:i - 1].min()
    ev[f"{prefix}new 52-week high"], ev[f"{prefix}new 52-week low"] = hi, lo
    return d, ev


def on_gold_days(d, flags):
    """Map events on another series to the first 18K trading day on or after them."""
    out = np.zeros(n, bool)
    for k in np.nonzero(flags)[0]:
        j = bisect_left(gd, d[k])
        if j < n:
            out[j] = True
    return out


events = {}
_, ev = series_events(gd, go, gh, gl, gc, "")
events.update({k: (v, "cross") for k, v in ev.items()})
for inst, prefix in (("price_dollar_rl", "DOLLAR "), ("ons", "WORLD GOLD ")):
    d, o, h, l, c = arrays(inst)
    _, ev = series_events(d, o, h, l, c, prefix)
    events.update({k: (on_gold_days(d, v), "cross") for k, v in ev.items()})
for fn in talib.get_function_groups()["Pattern Recognition"]:
    out = getattr(talib, fn)(go, gh, gl, gc)
    name = fn[3:].lower()
    events[f"candle {name} bullish"] = ((out > 0) & real4, "candle")
    events[f"candle {name} bearish"] = ((out < 0) & real4, "candle")


def in_period(period):
    return np.array([period[0] <= x <= period[1] for x in gd])


def stats(mask, pool):
    """Event mean vs bootstrap of random pool days; returns dict per measure."""
    idx = np.nonzero(mask & pool & ~np.isnan(fwd[PRIMARY]))[0]
    pool_idx = np.nonzero(pool & ~np.isnan(fwd[PRIMARY]))[0]
    res = {"n": len(idx)}
    if len(idx) == 0:
        return res
    for h in HORIZONS:
        v = fwd[h][idx]; v = v[~np.isnan(v)]
        base = fwd[h][pool_idx]; base = base[~np.isnan(base)]
        res[f"m{h}"] = v.mean() - base.mean() if len(v) else np.nan
        res[f"up{h}"] = (v > 0).mean() * 100 - (base > 0).mean() * 100 if len(v) else np.nan
    res["pull"] = (np.nanmean(pull[idx]) - np.nanmean(pull[pool_idx])) * 100
    if len(idx) >= 5:
        obs = fwd[PRIMARY][idx].mean()
        base = fwd[PRIMARY][pool_idx]
        boots = np.array([base[np.random.randint(0, len(base), len(idx))].mean() for _ in range(BOOT)])
        res["p"] = min(1.0, 2 * min((boots >= obs).mean(), (boots <= obs).mean()) + 1 / BOOT)
    return res


np.random.seed(7)
ins_pool_all, hold_pool_all = in_period(IN_SAMPLE), in_period(HOLDOUT)
rows = []
for name, (mask, kind) in events.items():
    ins_pool = ins_pool_all & (real4 if kind == "candle" else True)
    hold_pool = hold_pool_all & (real4 if kind == "candle" else True)
    a, b = stats(mask, ins_pool), stats(mask, hold_pool)
    if a["n"] >= 8 and "p" in a:
        rows.append((name, kind, a, b))

# Benjamini-Hochberg on the in-sample primary p-values
rows.sort(key=lambda r: r[2]["p"])
m = len(rows)
qvals = [0.0] * m
prev = 1.0
for k in range(m - 1, -1, -1):
    prev = min(prev, rows[k][2]["p"] * m / (k + 1))
    qvals[k] = prev

print(f"{m} event types with 8+ in-sample cases; primary measure: 18K's {PRIMARY}-day move vs the same period's base")
print(f"{'event':44} {'n in':>5} {'20d excess':>10} {'up%':>6} {'5%pull':>7} {'p':>6} {'q':>6} | {'n hold':>6} {'20d excess':>10} {'up%':>6} | verdict")
passed = []
for k, (name, kind, a, b) in enumerate(rows):
    hold_ok = b.get("n", 0) >= 10 and not np.isnan(b.get("m20", np.nan)) and \
        np.sign(b["m20"]) == np.sign(a["m20"]) and abs(b["m20"]) >= abs(a["m20"]) / 2
    verdict = "PREDICTIVE" if qvals[k] <= 0.10 and hold_ok else ("in-sample only" if qvals[k] <= 0.10 else "")
    if verdict == "PREDICTIVE":
        passed.append(name)
    if k < 40 or verdict:
        print(f"{name[:44]:44} {a['n']:5} {a['m20']:+9.2f}% {a['up20']:+5.0f}  {a['pull']:+6.0f}  {a['p']:6.3f} {qvals[k]:6.3f} | "
              f"{b.get('n', 0):6} {b.get('m20', float('nan')):+9.2f}% {b.get('up20', float('nan')):+5.0f} | {verdict}")
print(f"\nPassed (q <= 0.10 in-sample and confirmed on 2024-2026): {len(passed)}")
for name in passed:
    print("  ", name)
json.dump([{"name": r[0], "kind": r[1], "in": r[2], "hold": r[3], "q": qvals[k]} for k, r in enumerate(rows)],
          open(os.path.join(HERE, "data", "rd_events_result.json"), "w"), default=float, indent=1)
