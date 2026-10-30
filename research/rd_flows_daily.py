"""The funds' money flow against what followed, at daily resolution (SP_D_HANDOFF.md section 81; descriptive).
77.8's table read fipiran's 588 unit steps, weekly from 2020-03; research/fetch_fipiran_gap.py made them daily.

For each day: the gold funds' net creations over its last 5 trading days, as a share of net assets (the sum of
units_flow, with 4 or more of the 5 present). Days are cut into fifths over the whole span (descriptive: the
cut-points see every day) and, after each fifth: 18K's next 20 and 40 trading days, how often it is up after
20, and a fall of 10% or more within 40 (E-5's target). Then the same by sub-span, because a pattern that lives
in one era is not a pattern.

    python research/rd_flows_daily.py
"""

import json
import os
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rd_fall_risk as e5  # noqa: E402

SPANS = (("2019-2021", "2019-01-01", "2021-12-31"), ("2022-2023", "2022-01-01", "2023-12-31"),
         ("2024-2026", "2024-01-01", "2100-01-01"))


def table(rows, idx, flow, y, label):
    fwd = lambda i, h: rows[i + h]["g18"] / rows[i]["g18"] - 1 if i + h < len(rows) else None  # noqa: E731
    days = [i for i in idx if flow[i] is not None and fwd(i, 40) is not None]
    if len(days) < 50:
        print(f"{label}: {len(days)} days, too few")
        return
    cuts = [st.quantiles([flow[i] for i in days], n=5)[k] for k in range(4)]
    print(f"{label}: {len(days)} days")
    for name, keep in (("heavy redemptions (bottom fifth)", lambda v: v <= cuts[0]),
                       ("middle three fifths", lambda v: cuts[0] < v <= cuts[3]),
                       ("heavy creations (top fifth)", lambda v: v > cuts[3])):
        g = [i for i in days if keep(flow[i])]
        r20 = [fwd(i, 20) for i in g]
        falls = [y[i] for i in g if y[i] is not None]
        print(f"  {name:33s} {len(g):4d} days  20d {st.mean(r20):+.1%}  up {sum(r > 0 for r in r20) / len(r20):.0%}"
              f"  40d {st.mean(fwd(i, 40) for i in g):+.1%}  10% fall {sum(falls) / len(falls):.0%}")


def main():
    with open(os.path.join(HERE, "data", "panel.json"), encoding="utf-8") as f:
        rows = json.load(f)["rows"]
    units = [r.get("units_flow") for r in rows]
    flow = []
    for i in range(len(rows)):
        last = units[max(0, i - 4):i + 1]
        held = [v for v in last if v is not None]
        flow.append(sum(held) * 5 / len(held) if len(last) == 5 and len(held) >= 4 else None)
    y = e5.target(rows)
    table(rows, range(len(rows)), flow, y, "All, 2019-2026")
    for name, a, b in SPANS:
        table(rows, [i for i, r in enumerate(rows) if a <= r["date"] <= b], flow, y, name)


if __name__ == "__main__":
    main()
