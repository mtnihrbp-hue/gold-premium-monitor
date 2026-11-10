"""What a plain gold / fixed-income mix gives, on the harness of section 66 (no model): wealth and worst drop by gold share
(SP_D_HANDOFF.md 109.6).

    python research/rd_mix_table.py
"""
import sys
from datetime import date

sys.path.insert(0, "research")
sys.stdout.reconfigure(encoding="utf-8")
import rd_benchmarks as b  # noqa: E402

SHARES = (1.0, 0.85, 0.7, 0.5, 0.3)
original = b.target


def patched(rule, closes, i, d, prev_d):
    if isinstance(rule, float):
        return rule if (prev_d is None or d.month != prev_d.month) else None
    return original(rule, closes, i, d, prev_d)


b.target = patched
gold, level = b.load()
PERIODS = b.PERIODS + (("ALL", date(2015, 3, 15), date(2026, 10, 1)),)
print("share  " + "   ".join(f"{p[0]:>18}" for p in PERIODS))
for share in SHARES:
    cells = []
    for name, start, end in PERIODS:
        wealth, moves, in_gold, s, e = b.simulate(share, gold, level, start, end)
        x, rate, dd, wy = b.stats(wealth, s, e)
        cells.append(f"{x:7.2f} {dd:7.1%} {rate:5.0%}")
    print(f"{share:4.0%}   " + "   ".join(cells))
print("(each cell: wealth from 1, worst drop, yearly rate)")
for rule in ("B4", "B5"):
    cells = []
    for name, start, end in PERIODS:
        wealth, moves, in_gold, s, e = b.simulate(rule, gold, level, start, end)
        x, rate, dd, wy = b.stats(wealth, s, e)
        cells.append(f"{x:7.2f} {dd:7.1%} {rate:5.0%}")
    print(f"{rule}     " + "   ".join(cells))
