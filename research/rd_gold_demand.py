"""Gold demand: what followed rushes into, and flights out of, the gold funds (SP-D, SP_D_HANDOFF.md
section 35.8). For Direction's GOLD DEMAND line (owner, 2026-10-15: "people are buying gold more (or
less ...) there is a rush, or its normal").

Rules, fixed before the run:
- Funds: the 18 gold funds of research/data/tsetmc_gold_funds.json; سافرون (saffron) excluded.
- Each day, over the funds that traded: individuals' buy value and buyers, sell value and sellers.
- Measures over the last 10 trading days (tablokhani's window, which production can read from GitHub):
    power10  (sum buy value / sum buyers) / (sum sell value / sum sellers): above 1, buyers bring more
             money each than sellers take
    net10    (sum buy value - sum sell value) / sum (buy value + sell value): individuals' net share
    crowd10  buyers over the 10 days against the 120 days before them: a rush of people buying
- Each day's rank against the earlier days only (expanding window, from 250 days of history).
- Bands: bottom 10% ("leaving"), top 10% ("rushing in"), and the rest ("normal"). Also 20%.
- Outcomes on tgju's 18K closes: the move over the next 20 trading days, and whether it fell 5% at
  any close within them. Compared with all days of the same era: 2019-2023 and 2024-2026 (the funds'
  flows before 2019 are thin).
"""

import json
import os
import pickle
import sys
from collections import defaultdict
from datetime import date

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))   # the pickle of tgju's series carries a panel
NOT_GOLD = {"51200575796028449"}          # سافرون
WINDOW, HORIZON, MIN_HISTORY = 10, 20, 250


def daily_flows():
    F = json.load(open(os.path.join(HERE, "data", "tsetmc_gold_funds.json"), encoding="utf-8"))
    agg = defaultdict(lambda: np.zeros(5))
    for code, fund in F.items():
        if code in NOT_GOLD:
            continue
        for f in fund["flows"]:
            s = str(f["recDate"])
            agg[date(int(s[:4]), int(s[4:6]), int(s[6:]))] += [float(f.get(k) or 0) for k in
                                                               ("buy_I_Value", "buy_I_Count", "sell_I_Value", "sell_I_Count")] + [1]
    return {d: a for d, a in agg.items() if a[1] and a[3] and a[2]}


def measures(flows):
    days = sorted(flows)
    a = np.array([flows[d][:4] for d in days])
    out = {}
    for i in range(WINDOW - 1, len(days)):
        bv, bc, sv, sc = a[i - WINDOW + 1:i + 1].sum(axis=0)
        prior = a[max(0, i - WINDOW - 119):i - WINDOW + 1, 1]
        crowd = (bc / WINDOW) / prior.mean() if len(prior) >= 60 and prior.mean() > 0 else np.nan
        out[days[i]] = ((bv / bc) / (sv / sc), (bv - sv) / (bv + sv), crowd)
    return out


def causal_rank(values):
    ranks = [None] * len(values)
    for i in range(MIN_HISTORY, len(values)):
        ranks[i] = float(np.mean(np.asarray(values[:i]) < values[i]) * 100)
    return ranks


def main(gold_pickle):
    G = pickle.load(open(gold_pickle, "rb"))["gold"]
    gdays, gclose = list(G[0]), np.array(G[3], dtype=float)
    pos = {d: k for k, d in enumerate(gdays)}
    m = measures(daily_flows())
    for name, idx in (("power10", 0), ("net10", 1), ("crowd10", 2)):
        days = [d for d in sorted(m) if d in pos and np.isfinite(m[d][idx])]
        vals = [m[d][idx] for d in days]
        ranks = causal_rank(vals)
        print(f"\n== {name}: {len(days)} days {days[0]} .. {days[-1]}; latest {vals[-1]:+.3f} (rank {ranks[-1]:.0f})")
        for era, lo, hi in (("2019-2023", date(2019, 1, 1), date(2023, 12, 31)), ("2024-2026", date(2024, 1, 1), date(2026, 12, 31))):
            rows = []
            for d, r in zip(days, ranks):
                k = pos[d]
                if r is None or not (lo <= d <= hi) or k + HORIZON >= len(gclose):
                    continue
                fwd = gclose[k + 1:k + HORIZON + 1]
                rows.append((r, (fwd[-1] / gclose[k] - 1) * 100, bool((fwd <= gclose[k] * 0.95).any())))
            if not rows:
                continue
            r_, move, drop = (np.array(x) for x in zip(*rows))
            line = f"  {era}: all days n={len(rows)} move {np.median(move):+.2f}% (mean {move.mean():+.2f}) drop5 {drop.mean():.0%}"
            print(line)
            for label, mask in (("bottom 10%", r_ < 10), ("bottom 20%", r_ < 20), ("middle", (r_ >= 20) & (r_ < 80)),
                                ("top 20%", r_ >= 80), ("top 10%", r_ >= 90)):
                if mask.sum() >= 10:
                    print(f"    {label:<10} n={mask.sum():>4}  move {np.median(move[mask]):+.2f}% (mean {move[mask].mean():+.2f})"
                          f"  drop5 {drop[mask].mean():.0%}  higher {np.mean(move[mask] > 0):.0%}")


if __name__ == "__main__":
    main(sys.argv[1])
