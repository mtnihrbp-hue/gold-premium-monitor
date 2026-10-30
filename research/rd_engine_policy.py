"""Study E-2, the engine's parts 4 and 5: the move to fixed income and the way back (SP_D_HANDOFF.md section
74.4; registered in 3b0995a before this run). Reads E-1's walk-forward forecasts (research/data/calm_forecasts.json).

Default 100% gold. Half into fixed income when the forecast volatility is at or below its q-quantile of the 500
days before and 18K's 60-day log return is at or below m; back to gold at the first of an upward break (k x the
forecast daily volatility x the square root of the days since entry), turbulence (5-day volatility above twice
the forecast at entry), Tether up 3% in 5 days, or 40 trading days. Decided at t's close, traded at t+1's; the
gold leg at a fee a side, fixed income 0.05% a side, the money idle 2 days each way. q, k and m chosen each
1 January on the years before, by wealth against holding gold.

    python research/rd_engine_policy.py
"""

import itertools
import json
import math
import os
import statistics as st
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
FI_FEE = 0.0005
TRANSIT = 2
LOOKBACK = 500
GRID = list(itertools.product((0.20, 0.33, 0.50), (1.0, 2.0), (0.0, float("inf"))))
FEES = (("WallGold 0.50%", 0.005), ("Daric 0.15%", 0.0015), ("Ayyareh 2%", 0.02))
TRAIN_FROM = date(2015, 3, 15)
PERIODS = (("P1", date(2018, 1, 1), date(2019, 12, 31)),
           ("P2", date(2020, 1, 1), date(2023, 12, 31)),
           ("P3", date(2024, 1, 1), date(2026, 10, 13)))


def load(model):
    with open(os.path.join(HERE, "data", "panel.json"), encoding="utf-8") as f:
        rows = json.load(f)["rows"]
    with open(os.path.join(HERE, "data", "calm_forecasts.json"), encoding="utf-8") as f:
        fc = json.load(f)
    d = [date.fromisoformat(r["date"]) for r in rows]
    g = [r["g18"] for r in rows]
    fi = [r["fi"] for r in rows]
    teth = [r["tether"] for r in rows]
    pred = [fc.get(r["date"], {}).get(model) for r in rows]
    rv5 = [fc.get(r["date"], {}).get("rv5") for r in rows]
    return d, g, fi, teth, pred, rv5


def simulate(data, start, end, params_by_year, fee):
    """Wealth from 1 at `start` to `end`; returns (wealth series, entries, days half in fixed income)."""
    d, g, fi, teth, pred, rv5 = data
    idx = [i for i in range(len(d)) if start <= d[i] <= end and fi[i]]
    gold, fixed, transit = 1.0, 0.0, []           # transit: [amount, "g" or "f", days left]
    state, entry, entry_sigma = "gold", None, None
    pending = None
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
            transit.append([x * (1 - fee) * (1 - FI_FEE), "f", TRANSIT])
            state, entry, entries = "half", i, entries + 1
        elif pending == "exit":
            x = fixed
            fixed = 0.0
            transit.append([x * (1 - FI_FEE) * (1 - fee), "g", TRANSIT])
            state, entry = "gold", None
        pending = None
        total = gold + fixed + sum(t[0] for t in transit)
        wealth.append(total)
        half_days += state == "half"
        q, k, m = params_by_year(d[i].year)
        if state == "gold":
            if pred[i] is None or i < 60:
                continue
            past = [pred[j] for j in range(max(0, i - LOOKBACK), i) if pred[j] is not None]
            if len(past) < 250:
                continue
            threshold = sorted(past)[int(q * (len(past) - 1))]
            ret60 = math.log(g[i] / g[i - 60]) if g[i - 60] else None
            if pred[i] <= threshold and ret60 is not None and ret60 <= m:
                pending, entry_sigma = "enter", math.exp(pred[i])
        else:
            if any(t[1] == "f" for t in transit):
                continue                           # the move has not landed yet
            days = i - entry
            up = math.log(g[i] / g[entry]) > k * entry_sigma * math.sqrt(max(days, 1))
            turbulent = rv5[i] is not None and math.exp(rv5[i]) > 2 * entry_sigma
            tether = teth[i] and i >= 5 and teth[i - 5] and teth[i] / teth[i - 5] - 1 > 0.03
            if up or turbulent or tether or days >= 40:
                pending = "exit"
    return wealth, entries, half_days / max(1, len(idx))


def hold(data, start, end):
    d, g, fi = data[0], data[1], data[2]
    idx = [i for i in range(len(d)) if start <= d[i] <= end and fi[i]]
    return [g[i] / g[idx[0]] for i in idx]


def worst_drop(w):
    peak, dd = w[0], 0.0
    for x in w:
        peak = max(peak, x)
        dd = min(dd, x / peak - 1)
    return dd


def choose(data, year, fee):
    """The grid's best on 2015-03-15 to the year before, by wealth against holding gold."""
    end = date(year - 1, 12, 31)
    base = hold(data, TRAIN_FROM, end)[-1]
    best, best_ratio = GRID[0], -1
    for params in GRID:
        w, _, _ = simulate(data, TRAIN_FROM, end, lambda y, p=params: p, fee)
        ratio = w[-1] / base
        if ratio > best_ratio:
            best, best_ratio = params, ratio
    return best, best_ratio


def main():
    for model in ("X", "H"):
        data = load(model)
        print(f"\n=== forecasts of model {model} ===")
        for label, fee in FEES:
            chosen = {y: choose(data, y, fee) for y in range(2018, 2027)}
            params = lambda y: chosen[y][0]
            wins = 0
            print(f"-- {label} a side" + ("  (the test)" if fee == 0.005 else ""))
            for name, a, b in PERIODS:
                w, entries, share = simulate(data, a, b, params, fee)
                h = hold(data, a, b)
                more, dd, hdd = w[-1] / h[-1] - 1, worst_drop(w), worst_drop(h)
                ok = more > 0 and dd >= hdd
                wins += ok
                print(f"   {name}: wealth {w[-1]:6.2f} against holding {h[-1]:6.2f} ({more:+.1%}); worst drop "
                      f"{dd:.1%} against {hdd:.1%}; {entries} entries, half in fixed income {share:.0%} of days"
                      f"{'  WIN' if ok else ''}")
            if fee == 0.005:
                print("   chosen each year (q, k, m; training ratio to holding):",
                      {y: (c[0][0], c[0][1], 'none' if c[0][2] == float('inf') else c[0][2], round(c[1], 3))
                       for y, c in chosen.items()})
                print(f"   TEST (Eb-5): {wins} of 3 periods -> {'PASS' if wins >= 2 else 'no'}")


if __name__ == "__main__":
    main()
