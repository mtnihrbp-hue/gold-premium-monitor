"""Study E-3, phase c: the move and the way back made slower (SP_D_HANDOFF.md section 74.7; registered in
ef8419d before this run).

Half into fixed income when E-1's model-X forecast is at or below its q-quantile of the 500 days before on
`confirm` days running and 18K's 60-day log return is at or below m. Back to gold on the hard stop (3 x the
forecast daily volatility x the square root of the days in) at any time, or, after `min_stay` days, on an
upward break at k, turbulence, Tether above its threshold, or 40 days. 96 variants, chosen each 1 January on the
years before; a year is held in gold when none beat holding on them.

    python research/rd_engine_policy2.py
"""

import itertools
import math
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rd_engine_policy as e2  # noqa: E402 -- the same data, costs, periods and helpers

HARD_K = 3.0
GRID = list(itertools.product((0.20, 0.33), (1, 5), (0, 10), (1.5, 2.5), (0.03, 0.06, None), (0.0, float("inf"))))
HOLD = None                                    # "held in gold this year"


def thresholds(data, q):
    """The q-quantile of the forecasts of the 500 days before, for every day (None until 250 are known)."""
    pred = data[4]
    out = [None] * len(pred)
    for i in range(len(pred)):
        past = [pred[j] for j in range(max(0, i - e2.LOOKBACK), i) if pred[j] is not None]
        if len(past) >= 250:
            out[i] = sorted(past)[int(q * (len(past) - 1))]
    return out


def simulate(data, start, end, params_by_year, fee, thr):
    d, g, fi, teth, pred, rv5 = data
    idx = [i for i in range(len(d)) if start <= d[i] <= end and fi[i]]
    gold, fixed, transit = 1.0, 0.0, []
    state, entry, sigma, pending, run = "gold", None, None, None, 0
    wealth, entries, half_days = [], 0, 0
    for n, i in enumerate(idx):
        if n:
            p = idx[n - 1]
            gold *= g[i] / g[p]
            fixed *= fi[i] / fi[p] if fi[p] else 1.0
        for t in transit:
            t[2] -= 1
        for amount, dest, left in [t for t in transit if t[2] <= 0]:
            if dest == "g":
                gold += amount
            else:
                fixed += amount
        transit = [t for t in transit if t[2] > 0]
        if pending == "enter":
            x = gold / 2
            gold -= x
            transit.append([x * (1 - fee) * (1 - e2.FI_FEE), "f", e2.TRANSIT])
            state, entry, entries = "half", i, entries + 1
        elif pending == "exit":
            x = fixed
            fixed = 0.0
            transit.append([x * (1 - e2.FI_FEE) * (1 - fee), "g", e2.TRANSIT])
            state, entry = "gold", None
        pending = None
        wealth.append(gold + fixed + sum(t[0] for t in transit))
        half_days += state == "half"
        params = params_by_year(d[i].year)
        if params is HOLD:
            run = 0
            if state == "half" and not any(t[1] == "f" for t in transit):
                pending = "exit"
            continue
        q, confirm, min_stay, k, tether_at, m = params
        if state == "gold":
            calm = pred[i] is not None and thr[q][i] is not None and pred[i] <= thr[q][i]
            run = run + 1 if calm else 0
            if run >= confirm and i >= 60 and math.log(g[i] / g[i - 60]) <= m:
                pending, sigma, run = "enter", math.exp(pred[i]), 0
        else:
            if any(t[1] == "f" for t in transit):
                continue
            days = i - entry
            rise = math.log(g[i] / g[entry])
            if rise > HARD_K * sigma * math.sqrt(max(days, 1)):
                pending = "exit"
                continue
            if days < min_stay:
                continue
            up = rise > k * sigma * math.sqrt(max(days, 1))
            turbulent = rv5[i] is not None and math.exp(rv5[i]) > 2 * sigma
            tether = (tether_at is not None and teth[i] and i >= 5 and teth[i - 5]
                      and teth[i] / teth[i - 5] - 1 > tether_at)
            if up or turbulent or tether or days >= 40:
                pending = "exit"
    return wealth, entries, half_days / max(1, len(idx))


def choose(data, year, fee, thr):
    end = date(year - 1, 12, 31)
    base = e2.hold(data, e2.TRAIN_FROM, end)[-1]
    best, best_ratio = HOLD, 1.0
    for params in GRID:
        w, _, _ = simulate(data, e2.TRAIN_FROM, end, lambda y, p=params: p, fee, thr)
        ratio = w[-1] / base
        if ratio > best_ratio:
            best, best_ratio = params, ratio
    return best, best_ratio


def main():
    data = e2.load("X")
    thr = {q: thresholds(data, q) for q in (0.20, 0.33)}
    for label, fee in e2.FEES:
        chosen = {y: choose(data, y, fee, thr) for y in range(2018, 2027)}
        wins = 0
        print(f"-- {label} a side" + ("  (the test)" if fee == 0.005 else ""))
        for name, a, b in e2.PERIODS:
            w, entries, share = simulate(data, a, b, lambda y: chosen[y][0], fee, thr)
            h = e2.hold(data, a, b)
            more, dd, hdd = w[-1] / h[-1] - 1, e2.worst_drop(w), e2.worst_drop(h)
            ok = more > 0 and dd >= hdd
            wins += ok
            print(f"   {name}: wealth {w[-1]:6.2f} against holding {h[-1]:6.2f} ({more:+.1%}); worst drop {dd:.1%} "
                  f"against {hdd:.1%}; {entries} entries, half in fixed income {share:.0%} of days{'  WIN' if ok else ''}")
        print("   chosen each year:", {y: ("gold" if c[0] is HOLD else c[0], round(c[1], 3)) for y, c in chosen.items()})
        if fee == 0.005:
            print(f"   TEST (Eb-5): {wins} of 3 periods -> {'PASS' if wins >= 2 else 'no'}")


if __name__ == "__main__":
    main()
