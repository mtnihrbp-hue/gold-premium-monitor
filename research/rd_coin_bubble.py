"""The coin's bubble and the exchange's coin demand: do they foresee 18K? (SP-D, 2026-10-05)

Data: research/data/tsetmc_intraday/coin_certificates.json (fetch_tsetmc_intraday.py): the
bank-vault coin certificates (tamam sekeh tarh-e jadid) on the commodity exchange, 2018-2026.
An Emami coin holds 8.133 g at 900 per mille, 7.32 g of pure gold; 18K is 750 per mille, so its
gold is worth 7.32 x (18K's price per gram) / 0.75. The bubble: a certificate's price x 1000 (one
coin) over that, minus one. The certificates' price unit moved by powers of ten over the years
(readings near +1,000% before 2025 and +10,000% before 2021), so each reading is divided by the
power of ten that brings it into -40%..+500%. Days with over 1B toman traded only; across the
certificates, weighted by value traded.

Signals, each causal: the bubble against its own 250 days (z), the bubble's 5-day change, the
value traded against its 60 days (z), individuals' net buying of the certificates as a share of
value (and its 5-day sum). Targets: 18K's next 1, 5 and 20 days from the next day's close (the
exchange's data is public after its session), and gold over fixed income over 20 and 60 days.
"""
import json
import os
from bisect import bisect_right
from collections import defaultdict
from datetime import date

import numpy as np
from scipy.stats import rankdata

from rd_rebuy import X20, X60, c, d, n

HERE = os.path.dirname(os.path.abspath(__file__))
C = json.load(open(os.path.join(HERE, "data", "tsetmc_intraday", "coin_certificates.json"), encoding="utf-8"))
PURE = 8.133 * 0.900
gix = {x: i for i, x in enumerate(d)}

day_b, day_v, flow_net, flow_tot = defaultdict(float), defaultdict(float), defaultdict(float), defaultdict(float)
for sym, s in C.items():
    for p in s["prices"]:
        k = p["date"]
        dt = date(k // 10000, (k // 100) % 100, k % 100)
        i = gix.get(dt)
        if i is None or i < 1 or p["value"] < 1e10 or p["close"] <= 0:
            continue
        r = p["close"] * 1000 / (PURE * c[i] / 0.75)
        r /= 10 ** np.floor(np.log10(r / 0.6))
        if not 0.6 <= r < 6:
            continue
        day_b[dt] += (r - 1) * p["value"]
        day_v[dt] += p["value"]
    for f in s["flows"]:
        k = f["recDate"]
        dt = date(k // 10000, (k // 100) % 100, k % 100)
        bi, si = float(f.get("buy_I_Value") or 0), float(f.get("sell_I_Value") or 0)
        bn = float(f.get("buy_N_Value") or 0)
        flow_net[dt] += bi - si
        flow_tot[dt] += bi + bn

days = sorted(k for k in day_v if day_v[k] > 0)
bub = np.full(n, np.nan)
val = np.full(n, np.nan)
net = np.full(n, np.nan)
for k in days:
    i = gix[k]
    bub[i] = day_b[k] / day_v[k] * 100
    val[i] = day_v[k]
    if flow_tot.get(k):
        net[i] = flow_net[k] / flow_tot[k] * 100
print(f"{len(days)} days with the coin's bubble, {days[0]} -> {days[-1]}")
for y in range(2018, 2027):
    sel = [bub[gix[k]] for k in days if k.year == y]
    if sel:
        print(f"   {y}: bubble median {np.median(sel):+5.1f}%, range {np.percentile(sel, 5):+5.1f}% to {np.percentile(sel, 95):+5.1f}%, "
              f"{len(sel)} days, value traded {np.nanmean([val[gix[k]] for k in days if k.year == y]) / 1e10:,.0f} B toman a day")


def last_known(a):
    """Carry the last reading forward over days without one (at most 5 days)."""
    out = np.full(n, np.nan)
    last, age = np.nan, 99
    for i in range(n):
        if np.isfinite(a[i]):
            last, age = a[i], 0
        else:
            age += 1
        out[i] = last if age <= 5 else np.nan
    return out


def z(a, w):
    out = np.full(n, np.nan)
    for i in range(w, n):
        x = a[i - w:i]
        x = x[np.isfinite(x)]
        if len(x) > w * 0.5 and np.isfinite(a[i]) and np.std(x) > 0:
            out[i] = (a[i] - np.mean(x)) / np.std(x)
    return out


B = last_known(bub)
SIG = {
    "bubble (z, 250 days)": z(B, 250),
    "bubble's 5-day change": np.concatenate([np.full(5, np.nan), B[5:] - B[:-5]]),
    "value traded (z, 60 days)": z(np.log(last_known(val)), 60),
    "individuals' net buying": last_known(net),
    "individuals' net, 5 days": np.array([np.nanmean(net[max(0, i - 4):i + 1]) if np.isfinite(net[max(0, i - 4):i + 1]).any()
                                          else np.nan for i in range(n)]),
}


def fwd_next(h):
    out = np.full(n, np.nan)
    out[:n - 1 - h] = (c[1 + h:] / c[1:n - h] - 1) * 100
    return out


R = {"18K 1d": fwd_next(1), "18K 5d": fwd_next(5), "18K 20d": fwd_next(20), "gold-FI 20d": X20, "gold-FI 60d": X60}
P5 = np.concatenate([np.full(5, np.nan), (c[5:] / c[:-5] - 1) * 100])
P20 = np.concatenate([np.full(20, np.nan), (c[20:] / c[:-20] - 1) * 100])
rng = np.random.default_rng(13)
PERIODS = (("2018-2021", date(2018, 7, 1), date(2021, 12, 31)), ("2022-2026", date(2022, 1, 1), date(2026, 12, 31)))


def partial_ic(s, y, sel):
    ok = sel & np.isfinite(s) & np.isfinite(y) & np.isfinite(P5) & np.isfinite(P20)
    if ok.sum() < 150:
        return np.nan, np.nan
    rs, ry = rankdata(s[ok]) / ok.sum(), rankdata(y[ok]) / ok.sum()
    X = np.column_stack([np.ones(ok.sum()), rankdata(P5[ok]) / ok.sum(), rankdata(P20[ok]) / ok.sum()])
    res = lambda v: v - X @ np.linalg.lstsq(X, v, rcond=None)[0]
    a, b = res(rs), res(ry)
    v = np.corrcoef(a, b)[0, 1]
    m = ok.sum()
    null = [np.corrcoef(np.roll(a, rng.integers(60, m - 60)), b)[0, 1] for _ in range(300)]
    return v, np.mean(np.abs(null) >= abs(v))


print("\nrank correlation after removing 18K's own last 5 and 20 days (luck in brackets)")
for name, s in SIG.items():
    cells = []
    for label, lo, hi in PERIODS:
        sel = np.array([lo <= x <= hi for x in d])
        for t in ("18K 5d", "18K 20d", "gold-FI 60d"):
            v, p = partial_ic(s, R[t], sel)
            cells.append(f"{label} {t} {v:+.2f} ({p * 100:3.0f}%)" if np.isfinite(v) else f"{label} {t}   -")
    print(f"   {name:27} " + "  ".join(cells))

print("\ngold over fixed income in the next 60 days, by fifth of the bubble's z (low -> high)")
for label, lo, hi in PERIODS:
    s = SIG["bubble (z, 250 days)"]
    sel = np.array([lo <= x <= hi for x in d]) & np.isfinite(s) & np.isfinite(X60)
    q = np.quantile(s[sel], [0.2, 0.4, 0.6, 0.8])
    bins = np.digitize(s[sel], q)
    print(f"   {label}: " + "  ".join(f"{np.mean(X60[sel][bins == k]):+6.1f}%" for k in range(5)) + f"   ({sel.sum()} days)")
