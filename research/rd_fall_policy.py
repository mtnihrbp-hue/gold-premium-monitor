"""E-6, the move on the risk of a fall (SP_D_HANDOFF.md section 77.2; registered in 05f1586 before this run).

Half into fixed income when E-5's probability of a 10% fall within 40 days is at or above a threshold, chosen
each 1 January on the years before from {0.30, 0.40, 0.50} by wealth against holding gold (the year in gold if
none beat holding). Back to gold when the probability falls below half the threshold after a 10-day minimum
stay, or at once on the hard stop (3 x the forecast daily volatility x the square root of the days in).
WallGold's 0.50% a side, fixed income 0.05%, 2 days idle each way. Run for R10 and R3.

    python research/rd_fall_policy.py
"""

import json
import math
import os
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rd_engine_policy as e2  # noqa: E402 -- the data loader, costs, periods, holding and worst drop

THRESHOLDS = (0.30, 0.40, 0.50)
MIN_STAY, HARD_K = 10, 3.0


def simulate(data, risk, start, end, threshold_by_year, fee):
    d, g, fi = data[0], data[1], data[2]
    pred = data[4]
    idx = [i for i in range(len(d)) if start <= d[i] <= end and fi[i]]
    gold, fixed, transit = 1.0, 0.0, []
    state, entry, sigma, pending = "gold", None, None, None
    wealth, entries, half = [], 0, 0
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
        half += state == "half"
        th = threshold_by_year(d[i].year)
        r = risk.get(d[i].isoformat())
        if th is None:
            if state == "half" and not any(t[1] == "f" for t in transit):
                pending = "exit"
            continue
        if state == "gold":
            if r is not None and r >= th:
                pending = "enter"
                sigma = math.exp(pred[i]) if pred[i] is not None else 0.015
        else:
            if any(t[1] == "f" for t in transit):
                continue
            days = i - entry
            if math.log(g[i] / g[entry]) > HARD_K * sigma * math.sqrt(max(days, 1)):
                pending = "exit"
            elif days >= MIN_STAY and r is not None and r < th / 2:
                pending = "exit"
    return wealth, entries, half / max(1, len(idx))


def choose(data, risk, year, fee):
    end = date(year - 1, 12, 31)
    base = e2.hold(data, e2.TRAIN_FROM, end)[-1]
    best, best_ratio = None, 1.0
    for th in THRESHOLDS:
        w, _, _ = simulate(data, risk, e2.TRAIN_FROM, end, lambda y, t=th: t, fee)
        if w[-1] / base > best_ratio:
            best, best_ratio = th, w[-1] / base
    return best, best_ratio


def main():
    with open(os.path.join(HERE, "data", "fall_risk.json"), encoding="utf-8") as f:
        fr = json.load(f)
    data = e2.load("X")
    calm_b = json.load(open(os.path.join(HERE, "data", "calm_forecasts_b.json"), encoding="utf-8"))
    data = data[:4] + ([calm_b.get(dd.isoformat(), {}).get("X") for dd in data[0]],) + data[5:]
    for model in ("R10", "R3"):
        risk = {k: v.get(model) for k, v in fr.items() if v.get(model) is not None}
        for label, fee in e2.FEES:
            chosen = {y: choose(data, risk, y, fee) for y in range(2018, 2027)}
            wins = 0
            print(f"-- {model}, {label} a side" + ("  (the test)" if fee == 0.005 else ""))
            for name, a, b in e2.PERIODS:
                w, entries, share = simulate(data, risk, a, b, lambda y: chosen[y][0], fee)
                h = e2.hold(data, a, b)
                more, dd, hdd = w[-1] / h[-1] - 1, e2.worst_drop(w), e2.worst_drop(h)
                ok = more > 0 and dd >= hdd
                wins += ok
                print(f"   {name}: wealth {w[-1]:6.2f} against {h[-1]:6.2f} ({more:+.1%}); worst drop {dd:.1%} against {hdd:.1%};"
                      f" {entries} entries; half in fixed income {share:.0%} of days{'  WIN' if ok else ''}")
            print("   chosen:", {y: (c[0], round(c[1], 3)) for y, c in chosen.items()})
            if fee == 0.005:
                print(f"   TEST (Eb-5): {wins} of 3 -> {'PASS' if wins >= 2 else 'no'}")


if __name__ == "__main__":
    main()
