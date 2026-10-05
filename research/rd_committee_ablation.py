"""Does each member help the committee? Leave-one-out over every two-year window (SP-D, 2026-10-05).

The committee of rd_committee_2y.py (the proposed weights, out at 60% of the weight with a view,
back at 30%), run on the 18 two-year windows that start each Persian quarter from 1399 Q2 to 1403
Q3, once with every member and once without each member in turn; and the money-flow member at
the weight its exit record suggests (1.5 instead of 0.5).
"""
from collections import defaultdict
from datetime import date

import numpy as np

import rd_committee_2y as R


def make_committee(weights, leave=0.6, back=0.3):
    def factory(idx):
        state = {"out": False}

        def f(i):
            opinion = {m: R.LEAN[m][i] for m in R.MEMBERS if R.LEAN[m][i] != 0 and weights.get(m, 0) > 0}
            share = 0.0 if len(opinion) < 2 else \
                sum(weights[m] for m, v in opinion.items() if v == -1) / sum(weights[m] for m in opinion)
            if not state["out"] and share >= leave:
                state["out"] = True
            elif state["out"] and share <= back:
                state["out"] = False
            return state["out"]
        return f
    return factory



def main():
    VARIANTS = [("all members", dict(R.PROPOSED))]
    for m in R.MEMBERS:
        w = dict(R.PROPOSED)
        w[m] = 0
        VARIANTS.append((f"without {m}", w))
    w = dict(R.PROPOSED)
    w["money flow"] = 1.5
    VARIANTS.append(("money flow at 1.5", w))
    w = dict(R.PROPOSED)
    w["chartist"] = 0.5
    VARIANTS.append(("chartist at 0.5", w))

    starts = [i for i in range(1, R.n) if date(2020, 6, 1) <= R.d[i] <= date(2024, 10, 5) and R.QL[i] != R.QL[i - 1]]
    table = defaultdict(list)
    for si in starts:
        st = R.d[si]
        en = date(st.year + 2, st.month, min(st.day, 28))
        E = R.evaluate(st, en, extra=[(name, make_committee(wt)) for name, wt in VARIANTS])
        hv = E["res"]["hold (the bar)"]["end"]
        for name, _ in VARIANTS:
            table[name].append(E["res"][name]["end"] / hv - 1)
    last = R.evaluate(R.START, R.END, extra=[(name, make_committee(wt)) for name, wt in VARIANTS])
    hv = last["res"]["hold (the bar)"]["end"]
    print(f"{len(starts)} two-year windows; the committee with the proposed weights, one member removed at a time")
    print("   variant                        median vs hold   beat holding in   worst     best    | the last two years")
    for name, _ in VARIANTS:
        v = np.array(table[name]) * 100
        print(f"   {name:30} {np.median(v):+7.1f}%        {np.mean(v > 0.05) * 100:4.0f}% of windows  {v.min():+6.1f}%  {v.max():+6.1f}%"
              f"  | {(last['res'][name]['end'] / hv - 1) * 100:+6.1f}%")


if __name__ == "__main__":
    main()
