"""The gold funds' intraday data: volume profile, LIT and the session's shape, against 18K (SP-D, 2026-10-05).

Data: research/data/tsetmc_intraday/{insCode}.json (fetch_tsetmc_intraday.py): Ayyar's one-minute
bars (price, volume, value, trades) 2023-10 -> 2026-10. The session ran 12:00-15:00 Tehran until
2025 and runs 12:00-18:00 now.

Per fund day, at the session's close:
  close vs VWAP          the close against the day's volume-weighted price
  close in range         where the close sits in the day's low..high (0 low, 1 high)
  value-area position    the close against the day's value area (70% of the volume, 0.25% bins):
                         above it +1, inside 0, below -1
  POC migration          today's point of control against yesterday's (%)
  trend day              the price left the first 30 minutes' range and closed beyond it (+1 up,
                         -1 down)
  last hour              the last fifth of the session's minutes: its price move (%) and volume share
  sweep (LIT)            the day ran beyond yesterday's high and closed back under it (-1: buy-side
                         liquidity taken, bearish), or below yesterday's low and closed back over it
                         (+1: sell-side taken, bullish)
  volume surge           the day's value against its 20 days (z)
  20-day profile         the close against the value area of the last 20 sessions' minute volume

Targets: 18K (tgju) from day t's close and, to be safe about timing, from day t+1's close, 1 / 5 /
20 days on; gold over fixed income over 20 / 60 days. Rank correlation after removing 18K's own last
1, 5 and 20 days and the fund's own day; circular-shift bootstrap for luck.

Then, inside the day: does the fund's last hour lead the platforms' next hour? (production's hourly
readings, 2026-08 -> 10).
"""
import json
import os
import sys
from datetime import date, datetime, timedelta

import numpy as np
from scipy.stats import rankdata

from rd_rebuy import X20, X60, c, d, n

HERE = os.path.dirname(os.path.abspath(__file__))
INS = sys.argv[1] if len(sys.argv) > 1 else "34144395039913458"
F = json.load(open(os.path.join(HERE, "data", "tsetmc_intraday", f"{INS}.json"), encoding="utf-8"))
gix = {x: i for i, x in enumerate(d)}


def value_area(prices, vols, bin_pct=0.25, share=0.70):
    lo, hi = np.log(min(prices)), np.log(max(prices))
    step = np.log1p(bin_pct / 100)
    edges = np.arange(lo, hi + step, step)
    if len(edges) < 2:
        p = prices[0]
        return p, p, p
    k = np.clip(np.searchsorted(edges, np.log(prices)) - 1, 0, len(edges) - 2)
    mass = np.bincount(k, weights=vols, minlength=len(edges) - 1)
    poc = int(np.argmax(mass))
    a = b = poc
    total, got = mass.sum(), mass[poc]
    while got < share * total:
        up = mass[b + 1] if b + 1 < len(mass) else -1
        dn = mass[a - 1] if a > 0 else -1
        if up >= dn:
            b += 1
            got += mass[b]
        else:
            a -= 1
            got += mass[a]
    mid = lambda j: float(np.exp((edges[j] + edges[j + 1]) / 2))
    return mid(poc), mid(a), mid(b)


rows = []
keys = sorted(F["days"])
prev = None
hist = []          # (prices, vols) of the last 20 sessions
for key in keys:
    rec = F["days"][key]
    bars = rec.get("bars") or []
    bars = [b for b in bars if b[5] > 0]
    if len(bars) < 20:
        continue
    dt = date(int(key[:4]), int(key[4:6]), int(key[6:]))
    px = np.array([b[4] for b in bars], dtype=float)
    hi_ = max(b[2] for b in bars)
    lo_ = min(b[3] for b in bars)
    vol = np.array([b[5] for b in bars], dtype=float)
    val = np.array([b[6] for b in bars], dtype=float)
    close = px[-1]
    vwap = val.sum() / vol.sum()
    poc, val_lo, val_hi = value_area(px, vol)
    first = [b for b in bars if b[0] < bars[0][0] + 30]
    ib_hi, ib_lo = max(b[2] for b in first), min(b[3] for b in first)
    tail_n = max(3, len(bars) // 5)
    last_move = (px[-1] / px[-tail_n - 1] - 1) * 100 if len(px) > tail_n else np.nan
    last_share = vol[-tail_n:].sum() / vol.sum()
    r = {"date": dt, "close": close, "vwap_gap": (close / vwap - 1) * 100,
         "range_pos": (close - lo_) / (hi_ - lo_) if hi_ > lo_ else 0.5,
         "va_pos": 1 if close > val_hi else -1 if close < val_lo else 0,
         "trend_day": 1 if (hi_ > ib_hi and close > ib_hi) else -1 if (lo_ < ib_lo and close < ib_lo) else 0,
         "last_move": last_move, "last_share": last_share, "value": val.sum(), "poc": poc, "high": hi_, "low": lo_}
    if prev:
        r["poc_mig"] = (poc / prev["poc"] - 1) * 100
        r["sweep"] = -1 if (hi_ > prev["high"] and close < prev["high"]) else 1 if (lo_ < prev["low"] and close > prev["low"]) else 0
        r["day_ret"] = (close / prev["close"] - 1) * 100
    if len(hist) >= 10:
        allp = np.concatenate([h[0] for h in hist])
        allv = np.concatenate([h[1] for h in hist])
        p20, l20, h20 = value_area(allp, allv)
        r["va20_pos"] = 1 if close > h20 else -1 if close < l20 else 0
        r["va20_gap"] = (close / p20 - 1) * 100
    hist = (hist + [(px, vol)])[-20:]
    rows.append(r)
    prev = r

vals = np.array([r["value"] for r in rows])
for j, r in enumerate(rows):
    w = np.log(vals[max(0, j - 20):j])
    r["surge"] = (np.log(r["value"]) - w.mean()) / w.std() if j >= 10 and w.std() > 0 else np.nan

def main():
    print(f"{F['symbol']}: {len(rows)} sessions with minute bars, {rows[0]['date']} -> {rows[-1]['date']}")

    FEATS = ["vwap_gap", "range_pos", "va_pos", "poc_mig", "trend_day", "last_move", "last_share", "sweep", "surge",
             "va20_pos", "va20_gap"]
    S = {f: np.full(n, np.nan) for f in FEATS + ["day_ret"]}
    for r in rows:
        i = gix.get(r["date"])
        if i is None:
            continue
        for f in S:
            v = r.get(f)
            if v is not None and np.isfinite(v):
                S[f][i] = v


    def fwd(start_lag, h):
        out = np.full(n, np.nan)
        for i in range(n - start_lag - h):
            out[i] = (c[i + start_lag + h] / c[i + start_lag] - 1) * 100
        return out


    def back(k):
        out = np.full(n, np.nan)
        out[k:] = (c[k:] / c[:-k] - 1) * 100
        return out


    T = {"from today 1d": fwd(0, 1), "from today 5d": fwd(0, 5), "from today 20d": fwd(0, 20),
         "from tomorrow 1d": fwd(1, 1), "from tomorrow 5d": fwd(1, 5), "gold-FI 60d": X60}
    CTRL = [back(1), back(5), back(20), S["day_ret"]]
    rng = np.random.default_rng(17)


    def partial(s, y):
        ok = np.isfinite(s) & np.isfinite(y)
        for x in CTRL:
            ok &= np.isfinite(x)
        if ok.sum() < 120:
            return np.nan, np.nan, int(ok.sum())
        m = ok.sum()
        X = np.column_stack([np.ones(m)] + [rankdata(x[ok]) / m for x in CTRL])
        res = lambda v: v - X @ np.linalg.lstsq(X, v, rcond=None)[0]
        a, b = res(rankdata(s[ok]) / m), res(rankdata(y[ok]) / m)
        v = np.corrcoef(a, b)[0, 1]
        null = [np.corrcoef(np.roll(a, rng.integers(30, m - 30)), b)[0, 1] for _ in range(300)]
        return v, np.mean(np.abs(null) >= abs(v)), int(m)


    print("\n1. EACH MEASURE against 18K and gold over fixed income, after 18K's own moves and the fund's day (luck)")
    print("   " + " " * 14 + "".join(f"{t:>20}" for t in T))
    for f in FEATS:
        cells = []
        for t, y in T.items():
            v, p, m = partial(S[f], y)
            cells.append(f"{v:+.2f} ({p * 100:3.0f}%)" if np.isfinite(v) else "   -")
        print(f"   {f:14}" + "".join(f"{x:>20}" for x in cells) + f"   n={m}")

    # 2. inside the day: the fund's last hour against the platforms' next hour
    H = json.load(open(os.path.join(HERE, "data", "hourly.json")))
    bars_by_day = {k: F["days"][k].get("bars") or [] for k in keys}
    lead, own, nxt = [], [], []
    for a, b in zip(H[:-1], H[1:]):
        ta = datetime.fromisoformat(a["ts"]) + timedelta(hours=3, minutes=30)
        tb = datetime.fromisoformat(b["ts"]) + timedelta(hours=3, minutes=30)
        if tb.date() != ta.date() or not (0.7 <= (tb - ta).total_seconds() / 3600 <= 1.5):
            continue
        bars = bars_by_day.get(ta.strftime("%Y%m%d"))
        if not bars:
            continue
        hhmm = ta.hour * 100 + ta.minute
        before = [x for x in bars if x[0] <= hhmm]
        earlier = [x for x in bars if x[0] <= (ta - timedelta(hours=1)).hour * 100 + ta.minute]
        if not before or not earlier or before[-1][0] < hhmm - 10:
            continue
        pa = np.median([v for v in a["prices"].values() if v])
        pb = np.median([v for v in b["prices"].values() if v])
        lead.append((before[-1][4] / earlier[-1][4] - 1) * 100)
        nxt.append((pb / pa - 1) * 100)
        own.append(np.nan)
    print(f"\n2. INSIDE THE DAY: the fund's last hour against the platforms' next hour ({len(lead)} pairs, 2026-08 -> 10)")
    if len(lead) > 20:
        lead, nxt = np.array(lead), np.array(nxt)
        print(f"   correlation {np.corrcoef(lead, nxt)[0, 1]:+.2f}; when the fund rose over 0.5% in the hour, the platforms moved "
              f"{np.mean(nxt[lead > 0.5]):+.2f}% in the next ({(lead > 0.5).sum()} cases), when it fell over 0.5% "
              f"{np.mean(nxt[lead < -0.5]):+.2f}% ({(lead < -0.5).sum()}), otherwise {np.mean(nxt[np.abs(lead) <= 0.5]):+.2f}%")


if __name__ == "__main__":
    main()
