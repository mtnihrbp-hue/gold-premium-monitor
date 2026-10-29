"""The model's R&D, step 1: the simple alternatives (SP_D_HANDOFF.md section 66; rules registered in 66.1,
commit 7180768, before this script was run).

B1 hold gold, B2 hold fixed income, B3 70/30 rebalanced monthly, B4 the 50D MA trend rule (100% / 0%), B5 the
same in steps (100% / 40%). A decision at day t's close trades at t+1's close; a move costs 0.20% of the amount
and the money earns nothing for 2 trading days. Three periods, each from a wealth of 1.

    python research/rd_benchmarks.py
"""

import json
import os
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
COST = 0.0020           # a move: half of Daric's 0.30% round trip plus half of the fund's 0.10%
TRANSIT_DAYS = 2        # the moved money earns nothing meanwhile
MA_DAYS = 50
PERIODS = (("P1", date(2015, 3, 15), date(2019, 12, 31)),
           ("P2", date(2020, 1, 1), date(2023, 12, 31)),
           ("P3", date(2024, 1, 1), date(2026, 10, 1)))


def load():
    with open(os.path.join(HERE, "data", "tgju_history.json"), encoding="utf-8") as f:
        rows = json.load(f)["geram18"]
    gold = sorted((date.fromisoformat(r["date"]), float(r["close"])) for r in rows if r.get("close"))
    with open(os.path.join(ROOT, "src", "seed", "fixed_income.json"), encoding="utf-8") as f:
        level = {date.fromisoformat(k): float(v) for k, v in json.load(f)["level"].items()}
    return gold, level


def fi_on(level_days, level, day):
    """The fixed-income level carried forward to `day`."""
    import bisect
    i = bisect.bisect_right(level_days, day) - 1
    return level[level_days[i]] if i >= 0 else None


def target(rule, closes, i, d, prev_d):
    """The gold share rule `rule` asks for at day i's close."""
    if rule == "B1":
        return 1.0
    if rule == "B2":
        return 0.0
    if rule == "B3":
        return 0.7 if (prev_d is None or d.month != prev_d.month) else None   # None: no rebalance today
    ma = sum(closes[i - MA_DAYS + 1:i + 1]) / MA_DAYS
    above = closes[i] > ma
    if rule == "B4":
        return 1.0 if above else 0.0
    if rule == "B5":
        return 1.0 if above else 0.4
    raise ValueError(rule)


def simulate(rule, gold, level, start, end):
    level_days = sorted(level)
    days = [d for d, _ in gold]
    closes = [c for _, c in gold]
    idx = [i for i, d in enumerate(days) if start <= d <= end and i >= MA_DAYS]
    first = idx[0]
    w0 = target(rule, closes, first - 1, days[first - 1], None)
    w0 = 0.7 if rule == "B3" else w0
    g, f = w0, 1 - w0
    transit = []                       # [amount, "g" or "f", days left]
    pending = None                     # the share decided yesterday, traded today
    wealth, moves, in_gold = [], 0, 0.0
    prev_fi = fi_on(level_days, level, days[first])
    for k, i in enumerate(idx):
        d = days[i]
        if k:
            g *= closes[i] / closes[idx[k - 1]]
            fi = fi_on(level_days, level, d)
            if prev_fi and fi:
                f *= fi / prev_fi
            prev_fi = fi
        # money in transit arrives
        for t in transit:
            t[2] -= 1
        for amount, dest, left in [t for t in transit if t[2] <= 0]:
            if dest == "g":
                g += amount
            else:
                f += amount
        transit = [t for t in transit if t[2] > 0]
        # yesterday's decision trades at today's close
        if pending is not None:
            total = g + f + sum(t[0] for t in transit)
            want_g = pending * total
            in_transit_g = sum(t[0] for t in transit if t[1] == "g")
            in_transit_f = sum(t[0] for t in transit if t[1] == "f")
            delta = want_g - (g + in_transit_g)
            if delta > 1e-9 and f > 1e-12:
                x = min(delta, f)
                f -= x
                transit.append([x * (1 - COST), "g", TRANSIT_DAYS])
                moves += 1
            elif delta < -1e-9 and g > 1e-12:
                x = min(-delta, g)
                g -= x
                transit.append([x * (1 - COST), "f", TRANSIT_DAYS])
                moves += 1
        total = g + f + sum(t[0] for t in transit)
        wealth.append(total)
        in_gold += g / total if total else 0
        prev_d = days[i - 1]
        pending = target(rule, closes, i, d, prev_d)
        if rule == "B3" and pending is not None:
            pending = 0.7
    return wealth, moves, in_gold / len(idx), days[idx[0]], days[idx[-1]]


def stats(wealth, start, end):
    peak, worst_dd = wealth[0], 0.0
    for w in wealth:
        peak = max(peak, w)
        worst_dd = min(worst_dd, w / peak - 1)
    worst_year = min((wealth[j] / wealth[j - 250] - 1 for j in range(250, len(wealth))), default=None)
    years = (end - start).days / 365.25
    rate = (wealth[-1] / wealth[0]) ** (1 / years) - 1
    return wealth[-1] / wealth[0], rate, worst_dd, worst_year


def main():
    gold, level = load()
    results = {}
    for name, start, end in PERIODS:
        print(f"\n{name}: {start} to {end}")
        print(f"{'rule':5} {'wealth':>8} {'a year':>8} {'worst drop':>11} {'worst 250d':>11} {'moves':>6} {'in gold':>8}")
        for rule in ("B1", "B2", "B3", "B4", "B5"):
            wealth, moves, share, s, e = simulate(rule, gold, level, start, end)
            x, rate, dd, wy = stats(wealth, s, e)
            results[(name, rule)] = (x, dd)
            print(f"{rule:5} {x:8.2f} {rate:8.1%} {dd:11.1%} {wy:11.1%} {moves:6d} {share:8.0%}")
    print("\nAgainst holding gold (B1): more wealth, and the worst drop no deeper")
    for rule in ("B2", "B3", "B4", "B5"):
        wins = [p for p, _, _ in PERIODS
                if results[(p, rule)][0] > results[(p, "B1")][0] and results[(p, rule)][1] >= results[(p, "B1")][1]]
        print(f"{rule}: {len(wins)} of 3 periods {wins}  -> {'beats' if len(wins) >= 2 else 'does not beat'} holding gold")


if __name__ == "__main__":
    main()
