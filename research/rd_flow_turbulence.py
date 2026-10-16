"""Money flow in turbulent times (SP-D, SP_D_HANDOFF.md section 37.6). The owner, 2026-10-16: the money flow is
precious; "this buying/selling power ... sits very well in the times of turbulence". Section 36 found the room's
money-flow vote has no edge once the saffron fund is out; this asks whether the same data carries information
when the market is in turmoil, which a vote cast on every day would dilute.

Rules, fixed before the run:
- Data: the 18 gold funds of research/data/tsetmc_gold_funds.json (saffron excluded), individuals' buy and sell
  value and counts per day; tgju's 18K closes.
- Readings over 7 trading days, each ranked against the trailing 250 days (analysis/gold_demand.py): money (net
  share), people (buyers against the 120 days before), size (money per buyer over money per seller). A reading
  is HIGH at rank >= 90, LOW below 10.
- Turbulent day (causal): 18K's 20-day realized volatility in the top 20% of its trailing 250 days, or 18K
  10% or more below its trailing 250-day high close.
- Episodes: consecutive turbulent days with the same reading state; measured from each episode's first day.
- Outcomes: 18K's move over the next 20 and 60 trading days, and whether it fell another 5% within 20 days;
  against all turbulent days and against all days, in 2019-2022 and 2023-2026.
"""
import json
import os
import pickle
import sys
from collections import defaultdict
from datetime import date

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
SAFFRON = "51200575796028449"
W, PRIOR, TRAIL = 7, 120, 250


def fund_days():
    F = json.load(open(os.path.join(HERE, "data", "tsetmc_gold_funds.json"), encoding="utf-8"))
    agg = defaultdict(lambda: np.zeros(4))
    for code, fund in F.items():
        if code == SAFFRON:
            continue
        for f in fund["flows"]:
            s = str(f["recDate"])
            agg[date(int(s[:4]), int(s[4:6]), int(s[6:]))] += [float(f.get(k) or 0) for k in
                                                               ("buy_I_Value", "buy_I_Count", "sell_I_Value", "sell_I_Count")]
    days = sorted(d for d, a in agg.items() if a[1] and a[3] and a[2])
    return days, np.array([agg[d] for d in days])


def readings(days, a):
    out = {}
    series = []
    for i in range(W + 59, len(a)):
        bv, bc, sv, sc = a[i - W + 1:i + 1].sum(axis=0)
        prior = a[max(0, i - W - PRIOR + 1):i - W + 1, 1]
        series.append((days[i], (bv - sv) / (bv + sv), (bc / W) / prior.mean(), (bv / bc) / (sv / sc)))
    vals = np.array([s[1:] for s in series])
    for j in range(TRAIL, len(series)):
        ranks = [np.mean(vals[j - TRAIL:j, col] < vals[j, col]) * 100 for col in range(3)]
        out[series[j][0]] = {name: ("HIGH" if r >= 90 else "LOW" if r < 10 else "NORMAL")
                             for name, r in zip(("money", "people", "size"), ranks)}
    return out


def main(pickle_path):
    G = pickle.load(open(pickle_path, "rb"))["gold"]
    gd, gc = list(G[0]), np.array(G[3], float)
    pos = {d: k for k, d in enumerate(gd)}
    lr = np.concatenate([[0], np.diff(np.log(gc))])
    vol = np.array([np.std(lr[max(1, k - 19):k + 1]) if k >= 20 else np.nan for k in range(len(gc))])
    turb = np.zeros(len(gc), bool)
    for k in range(270, len(gc)):
        vrank = np.mean(vol[k - 250:k] < vol[k])
        dd = gc[k] / gc[k - 250:k + 1].max() - 1
        turb[k] = vrank >= 0.8 or dd <= -0.10
    fwd = lambda k, n: (gc[k + n] / gc[k] - 1) * 100 if k + n < len(gc) else np.nan
    drop5 = lambda k: bool((gc[k + 1:k + 21] <= gc[k] * 0.95).any()) if k + 20 < len(gc) else None
    days, a = fund_days()
    R = readings(days, a)
    eras = (("2019-2022", date(2019, 1, 1), date(2022, 12, 31)), ("2023-2026", date(2023, 1, 1), date(2026, 12, 31)))
    for era, lo, hi in eras:
        ks = [pos[d] for d in sorted(R) if d in pos and lo <= d <= hi]
        tk = [k for k in ks if turb[k]]
        base_all = [fwd(k, 20) for k in ks if np.isfinite(fwd(k, 20))]
        base_t20 = [fwd(k, 20) for k in tk if np.isfinite(fwd(k, 20))]
        base_t60 = [fwd(k, 60) for k in tk if np.isfinite(fwd(k, 60))]
        base_td = [drop5(k) for k in tk if drop5(k) is not None]
        print(f"\n== {era}: {len(ks)} days, turbulent {len(tk)} ({len(tk) / max(1, len(ks)):.0%}). Next 20 days: all {np.median(base_all):+.2f}%, "
              f"turbulent {np.median(base_t20):+.2f}% (60 days {np.median(base_t60):+.2f}%), a further 5% drop {np.mean(base_td):.0%}")
        for name in ("money", "people", "size"):
            for state in ("HIGH", "LOW"):
                eps, prev = [], None
                for k in tk:
                    s = R[gd[k]][name]
                    if s == state and (prev is None or prev != k - 1):
                        eps.append(k)
                    prev = k if s == state else prev
                f20 = [fwd(k, 20) for k in eps if np.isfinite(fwd(k, 20))]
                f60 = [fwd(k, 60) for k in eps if np.isfinite(fwd(k, 60))]
                dr = [drop5(k) for k in eps if drop5(k) is not None]
                if len(f20) >= 3:
                    print(f"   {name:>6} {state:<4} episodes {len(eps):>3}: next 20 days {np.median(f20):+6.2f}% (higher {np.mean(np.array(f20) > 0):.0%}), "
                          f"60 days {np.median(f60) if f60 else float('nan'):+6.2f}%, a further 5% drop {np.mean(dr):.0%}")
                else:
                    print(f"   {name:>6} {state:<4} episodes {len(eps):>3}: too few")
    print("\nMay-June 2026, the owner's case:")
    for d in sorted(R):
        if date(2026, 4, 25) <= d <= date(2026, 6, 25) and d in pos and (R[d]["money"] != "NORMAL" or R[d]["size"] != "NORMAL" or R[d]["people"] != "NORMAL"):
            k = pos[d]
            print(f"   {d} 18K {gc[k] / 1e7:.2f}M turbulent={turb[k]} {R[d]} next 20d {fwd(k, 20):+.1f}% 60d {fwd(k, 60):+.1f}%")


if __name__ == "__main__":
    main(sys.argv[1])
