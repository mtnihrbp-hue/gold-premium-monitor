"""What the data says about the share of gold against fixed income (SP_D_HANDOFF.md section 71).

Descriptive, not a rule test: for each period, every fixed share of gold from 0% to 100% in steps of 10,
rebalanced monthly on the harness of section 66 (lag 1, a move costs 0.20%, 2 days idle), with its wealth and
worst drop; and the growth-optimal share of theory for a log-normal asset against a safe one,
f* = (mu + sigma^2 / 2 - r) / sigma^2, from the period's own daily figures. It is known only after the fact.

    python research/rd_allocation_frontier.py
"""

import math
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rd_benchmarks as h  # noqa: E402 -- the same data, costs and periods


def fixed_share(share, gold, level, start, end):
    """Wealth of a fixed `share` in gold, rebalanced on the first trading day of each month."""
    original = h.target

    def target(rule, closes, i, d, prev_d):
        return share if (prev_d is None or d.month != prev_d.month) else None

    h.target = target
    try:
        wealth, moves, in_gold, s, e = h.simulate("FIXED", gold, level, start, end)
    finally:
        h.target = original
    return wealth, moves, s, e


def main():
    gold, level = h.load()
    days = [d for d, _ in gold]
    closes = [c for _, c in gold]
    level_days = sorted(level)
    for name, start, end in h.PERIODS:
        idx = [i for i, d in enumerate(days) if start <= d <= end]
        g = [math.log(closes[i] / closes[i - 1]) for i in idx[1:]]
        f = []
        for a, b in zip(idx, idx[1:]):
            x, y = h.fi_on(level_days, level, days[a]), h.fi_on(level_days, level, days[b])
            if x and y:
                f.append(math.log(y / x))
        mu, r = sum(g) / len(g), sum(f) / len(f)
        sigma2 = sum((x - mu) ** 2 for x in g) / (len(g) - 1)
        fstar = (mu + sigma2 / 2 - r) / sigma2
        per_year = len(g) / ((end - start).days / 365.25)
        print(f"\n{name} {start} to {end}: gold {math.exp(mu * per_year) - 1:+.0%} a year (log mean), "
              f"volatility {math.sqrt(sigma2 * per_year):.0%} a year, fixed income {math.exp(r * per_year) - 1:+.0%};"
              f" growth-optimal share f* = {fstar:.1f} (above 1: all gold, no borrowing)")
        print(f"{'gold share':>10} {'wealth':>8} {'worst drop':>11} {'moves':>6}")
        for k in range(0, 11):
            share = k / 10
            wealth, moves, s, e = fixed_share(share, gold, level, start, end)
            x, rate, dd, wy = h.stats(wealth, s, e)
            print(f"{share:10.0%} {x:8.2f} {dd:11.1%} {moves:6d}")


if __name__ == "__main__":
    main()
