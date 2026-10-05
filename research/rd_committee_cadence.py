"""How much does the weekly committee's result depend on the day it decides? (SP-D, 2026-10-05)

The committee with the proposed weights, deciding every 5 trading days, at each of the five
offsets from the window's start, and every 10 and 20 days; on the 18 two-year windows."""
from collections import defaultdict
from datetime import date

import numpy as np

import rd_committee_2y as R
from rd_committee_ablation import make_committee


def every(k, offset):
    def factory(idx):
        inner = make_committee(dict(R.PROPOSED))(idx)
        held = {"v": False}
        start = idx[0]

        def f(i):
            v = inner(i)                       # the committee's own state moves every day
            if (i - start) % k == offset:
                held["v"] = v
            return held["v"]
        return f
    return factory


def main():
    VARIANTS = [("every day", every(1, 0))] + [(f"every {k} days, offset {o}", every(k, o)) for k, offs in
                                                ((5, range(5)), (10, range(10)), (20, (0, 5, 10, 15))) for o in offs]
    starts = [i for i in range(1, R.n) if date(2020, 6, 1) <= R.d[i] <= date(2024, 10, 5) and R.QL[i] != R.QL[i - 1]]
    table = defaultdict(list)
    for si in starts:
        st = R.d[si]
        E = R.evaluate(st, date(st.year + 2, st.month, min(st.day, 28)), extra=VARIANTS)
        hv = E["res"]["hold (the bar)"]["end"]
        for name, _ in VARIANTS:
            table[name].append(E["res"][name]["end"] / hv - 1)
    last = R.evaluate(R.START, R.END, extra=VARIANTS)
    hv = last["res"]["hold (the bar)"]["end"]
    print("   cadence                     median vs hold   beat holding in   worst    best   | last two years")
    for name, _ in VARIANTS:
        v = np.array(table[name]) * 100
        print(f"   {name:26} {np.median(v):+7.1f}%        {np.mean(v > 0.05) * 100:4.0f}% of windows  {v.min():+6.1f}%  {v.max():+6.1f}%"
              f" | {(last['res'][name]['end'] / hv - 1) * 100:+6.1f}%")


if __name__ == "__main__":
    main()
