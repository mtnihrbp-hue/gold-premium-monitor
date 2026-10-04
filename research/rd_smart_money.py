"""Smart money and hot money in the gold funds: do they foresee 18K? (SP-D, 2026-10-04)

The owner: "if we could like in data from Ayyar or similar platforms using the volume
profile, LIT and so on we can foresee the effect. By following the hot money or smart
money that would be a better call than solely relying on the news."

Data: research/data/tsetmc_gold_funds.json (fetch_tsetmc_gold_funds.py, from an Iranian
connection): 19 gold funds on the Tehran exchange, daily prices and the money flow split
between individuals (I, haghighi) and institutions (N, hoghooghi). Summed over the funds:

  inflow        individuals' net buying, share of the value traded (= institutions' net selling)
  inflow5       the same over 5 days
  power         buyer power: individuals' value per buyer / value per seller
  surge         value traded against its own 60 days (z-score of the log)
  fund move     the funds' value-weighted return that day

Entry is one trading day after the signal (the flows are published after the session), so
nothing here uses a number before it was public. Target: 18K (tgju) 1, 5 and 20 days on.
Rank correlation (IC) per period, and the 18K move after the top and bottom 10% of days.
"""
import json
import os
from collections import defaultdict
from datetime import date

import numpy as np
from scipy.stats import spearmanr

HERE = os.path.dirname(os.path.abspath(__file__))
F = json.load(open(os.path.join(HERE, "data", "tsetmc_gold_funds.json"), encoding="utf-8"))
T = json.load(open(os.path.join(HERE, "data", "tgju_history.json")))["geram18"]
gd = [date.fromisoformat(r["date"]) for r in T]
gc = np.array([float(r["close"]) for r in T])
gix = {d: i for i, d in enumerate(gd)}

day = defaultdict(lambda: defaultdict(float))
for fund in F.values():
    px = {p["date"]: p for p in fund["prices"]}
    prev = None
    for p in sorted(fund["prices"], key=lambda p: p["date"]):
        if prev and prev["close"] > 0 and p["value"] > 0:
            k = date(int(p["date"][:4]), int(p["date"][4:6]), int(p["date"][6:]))
            day[k]["move_w"] += (p["close"] / prev["close"] - 1) * p["value"]
            day[k]["move_v"] += p["value"]
        prev = p
    for f in fund["flows"]:
        s = str(f["recDate"])
        k = date(int(s[:4]), int(s[4:6]), int(s[6:]))
        for key in ("buy_I_Value", "sell_I_Value", "buy_N_Value", "sell_N_Value", "buy_I_Count", "sell_I_Count"):
            day[k][key] += float(f.get(key) or 0)

days = sorted(k for k in day if k in gix and day[k]["buy_I_Value"] + day[k]["buy_N_Value"] > 0)
print(f"{len(days)} fund days matched to 18K, {days[0]} -> {days[-1]}")
v = {k: day[k] for k in days}
total = np.array([v[k]["buy_I_Value"] + v[k]["buy_N_Value"] for k in days])
inflow = np.array([(v[k]["buy_I_Value"] - v[k]["sell_I_Value"]) for k in days]) / total * 100
power = np.array([(v[k]["buy_I_Value"] / v[k]["buy_I_Count"]) / (v[k]["sell_I_Value"] / v[k]["sell_I_Count"])
                  if v[k]["buy_I_Count"] and v[k]["sell_I_Count"] and v[k]["sell_I_Value"] else np.nan for k in days])
move = np.array([v[k]["move_w"] / v[k]["move_v"] * 100 if v[k]["move_v"] else np.nan for k in days])
n = len(days)
inflow5 = np.array([np.nansum((inflow * total)[max(0, i - 4):i + 1]) / total[max(0, i - 4):i + 1].sum() for i in range(n)])
lt = np.log(total)
surge = np.full(n, np.nan)
for i in range(60, n):
    w = lt[i - 60:i]
    surge[i] = (lt[i] - w.mean()) / w.std()

g = np.array([gix[k] for k in days])


def fwd(h):
    """18K from the close one trading day after the signal to h days after that."""
    out = np.full(n, np.nan)
    for j, i in enumerate(g):
        if i + 1 + h < len(gc):
            out[j] = (gc[i + 1 + h] / gc[i + 1] - 1) * 100
    return out


def same_day_18k():
    out = np.full(n, np.nan)
    for j, i in enumerate(g):
        if i >= 1:
            out[j] = (gc[i] / gc[i - 1] - 1) * 100
    return out


R = {h: fwd(h) for h in (1, 5, 20)}
SIG = {"inflow": inflow, "inflow5": inflow5, "power": power, "surge": surge, "fund move": move}
PERIODS = (("2019-2022", date(2019, 1, 1), date(2022, 12, 31)), ("2023-2026", date(2023, 1, 1), date(2027, 1, 1)))

print("\n1. RANK CORRELATION with 18K's next days (IC; |IC| under ~0.05 is noise on these samples)")
for name, s in SIG.items():
    cells = []
    for label, lo, hi in PERIODS:
        sel = np.array([lo <= k <= hi for k in days])
        for h, r in R.items():
            ok = sel & np.isfinite(s) & np.isfinite(r)
            if ok.sum() > 100:
                cells.append(f"{label} {h}d {spearmanr(s[ok], r[ok])[0]:+.2f}")
    print(f"   {name:10} " + "  ".join(cells))

print("\n2. THE 18K MOVE AFTER THE TOP / BOTTOM 10% OF DAYS (mean %, all days in brackets)")
for name, s in SIG.items():
    for label, lo, hi in PERIODS:
        sel = np.array([lo <= k <= hi for k in days]) & np.isfinite(s)
        if sel.sum() < 200:
            continue
        top, bot = np.nanquantile(s[sel], 0.9), np.nanquantile(s[sel], 0.1)
        cells = []
        for h, r in R.items():
            ok = sel & np.isfinite(r)
            cells.append(f"{h}d top {np.mean(r[ok & (s >= top)]):+.2f} bottom {np.mean(r[ok & (s <= bot)]):+.2f}"
                         f" (all {np.mean(r[ok]):+.2f})")
        print(f"   {name:10} {label}: " + " | ".join(cells))

print("\n3. WHO LEADS WHOM: the funds' move and 18K's (correlation)")
same = same_day_18k()
ok = np.isfinite(move) & np.isfinite(same)
print(f"   same day {np.corrcoef(move[ok], same[ok])[0, 1]:+.2f}")
ok = np.isfinite(move) & np.isfinite(R[1])
print(f"   the funds today, 18K tomorrow {np.corrcoef(move[ok], R[1][ok])[0, 1]:+.2f}")
prev18 = np.full(n, np.nan)
prev18[1:] = same[:-1]
ok = np.isfinite(move) & np.isfinite(prev18)
print(f"   18K yesterday, the funds today {np.corrcoef(prev18[ok], move[ok])[0, 1]:+.2f}")

# 4. robustness: is it 18K's own recent move in disguise, and is it more than luck?
from scipy.stats import rankdata  # noqa: E402


def past(k):
    out = np.full(n, np.nan)
    for j, i in enumerate(g):
        if i >= k:
            out[j] = (gc[i] / gc[i - k] - 1) * 100
    return out


def residual(y, xs):
    X = np.column_stack([np.ones(len(y))] + xs)
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    return y - X @ beta


P1, P5, P20 = past(1), past(5), past(20)
boot = np.random.default_rng(11)
print("\n4. ROBUSTNESS, 2019-2026: IC after removing 18K's own last 1/5/20 days, and a 20-day block bootstrap")
for name in ("power", "inflow5", "surge"):
    s = SIG[name]
    for h in (5, 20):
        r = R[h]
        ok = np.isfinite(s) & np.isfinite(r) & np.isfinite(P1) & np.isfinite(P5) & np.isfinite(P20) \
            & np.array([k >= date(2019, 1, 1) for k in days])
        rs = rankdata(s[ok]) / ok.sum()
        rr = rankdata(r[ok]) / ok.sum()
        ctrl = [rankdata(x[ok]) / ok.sum() for x in (P1, P5, P20)]
        ic = np.corrcoef(rs, rr)[0, 1]
        partial = np.corrcoef(residual(rs, ctrl), residual(rr, ctrl))[0, 1]
        m = ok.sum()
        null = []
        for _ in range(500):
            shift = boot.integers(60, m - 60)
            idx = (np.arange(m) + shift) % m
            null.append(np.corrcoef(residual(rs[idx], ctrl), residual(rr, ctrl))[0, 1])
        p = np.mean(np.abs(null) >= abs(partial))
        print(f"   {name:8} {h:2}d: IC {ic:+.2f}, after 18K's own moves {partial:+.2f}, luck would give this {p * 100:.0f}% of the time")
