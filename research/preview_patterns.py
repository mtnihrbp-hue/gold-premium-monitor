"""Preview of the chart with the pattern reader's findings (SP-D, SP_D_HANDOFF.md section 37.4): the last two
ranges, the EMA20 tests, the live flag and its target, on the 21:00 chart. Research only; nothing is wired."""
import os
import pickle
import sys

import numpy as np
import talib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
sys.path.insert(0, HERE)
import rd_patterns as P  # noqa: E402
from alerts.chart import render  # noqa: E402
from caluclator.technical import fibonacci, rally_legs, split_levels, swing_levels, trendlines  # noqa: E402
from timeutil import persian_day  # noqa: E402


def main(pickle_path, out_png):
    data = pickle.load(open(pickle_path, "rb"))
    d, h, l, c, sw, rngs, events = P.main(pickle_path)
    live = float(data["panel"].price)
    o = c.copy()                                   # the pickle holds high/low/close; the open is drawn as the close
    e20, e50 = talib.EMA(c, 20), talib.EMA(c, 50)
    usable = [True] * len(c)
    sup, res = split_levels(swing_levels(h, l, upto=len(c) - 1, usable=usable), live)
    last_two = rngs[-2:]
    boxes = [(d[s], d[e], lo, hi, f"range {persian_day(d[s])}-{persian_day(d[e])}") for s, e, lo, hi, _ in last_two]
    boxes[-1] = (d[last_two[-1][0]], d[-1], last_two[-1][2], last_two[-1][3], f"range since {persian_day(d[last_two[-1][0]])}")
    recent = [ev for ev in events if ev[0] >= last_two[0][0] - 3]     # the two ranges' span only
    marks, targets, lines = [], [], []
    for (k, kind, level, target, stop, _) in recent:
        if kind == "EMA20 TEST":
            marks.append((d[k], l[k], "EMA20 test"))
        elif kind == "FLAG":
            marks.append((d[k], c[k], "flag breakout"))
            alive = c[k + 1:].max() < target and c[k + 1:].min() > stop
            if alive:
                targets.append((target, "flag target"))
                lines.append(f"Flag breakout of {persian_day(d[k])}: its measured target is {target / 1e7:.2f}M "
                             f"while 18K stays above {stop / 1e7:.2f}M")
    s, e, lo, hi, _ = last_two[-1]
    tests = [d[k] for (k, kind, *_r) in recent if kind == "EMA20 TEST" and k >= s]
    head = (f"Sideways since {persian_day(d[s])} between {lo / 1e7:.2f}M and {hi / 1e7:.2f}M"
            + (f"; tested the 20-day on {persian_day(tests[-1])} and held" if tests else ""))
    png = render(d, o, h, l, c, ema20=e20, ema50=e50, supports=[x["price"] for x in sup[:2]],
                 resistances=[x["price"] for x in res[:1]], live=live, title="18K daily (preview: patterns)",
                 patterns={"boxes": boxes, "marks": marks, "targets": targets})
    open(out_png, "wb").write(png)
    print("\nREADING")
    print(head)
    for line in lines:
        print(line)
    print(f"A close above {hi / 1e7:.2f}M breaks out of the range; under {lo / 1e7:.2f}M breaks down.")
    print(f"\nchart -> {out_png}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
