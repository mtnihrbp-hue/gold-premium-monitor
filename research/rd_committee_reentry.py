"""Momentum signals as a fast way back to gold (SP-D, 2026-10-05).

The committee (proposed weights, its view moving daily, acted on every 10 / 20 days); while the swing
is in fixed income, it comes back to gold on any day the trigger member leans to gold (the volume
profile, the stock index), without waiting for the decision day."""
from collections import defaultdict
from datetime import date

import numpy as np

import rd_committee_2y as R
import rd_committee_stocks  # noqa: F401
import rd_vp_member  # noqa: F401
from rd_committee_ablation import make_committee
from rd_committee_veto import BASE
from rd_rebuy import fi_log


def reentry(k, offset, trig):
    def factory(idx):
        inner = make_committee(dict(BASE))(idx)
        held = {"v": False}
        start = idx[0]

        def f(i):
            v = inner(i)
            if (i - start) % k == offset:
                held["v"] = v
            elif held["v"] and any(R.LEAN[m][i] == 1 for m in trig):
                held["v"] = False
            return held["v"]
        return f
    return factory


TRIGS = (("no trigger", ()), ("volume profile", ("volume profile",)), ("stocks", ("stocks 20d",)),
         ("either", ("volume profile", "stocks 20d")))
R.AFRAN_LEVEL = R.af_level.copy()
for label, first, last, park in (("Afran windows from 2020", date(2020, 6, 1), date(2024, 10, 5), "afran"),
                                 ("index windows from 2018", date(2018, 1, 1), date(2024, 10, 5), "index")):
    R.af_level = R.AFRAN_LEVEL if park == "afran" else np.exp(np.nan_to_num(fi_log - np.nanmin(fi_log)))
    R.af_ret = np.zeros(R.n)
    R.af_ret[1:] = R.af_level[1:] / R.af_level[:-1] - 1
    variants = [(f"{name}|{k}|{o}", reentry(k, o, ts)) for name, ts in TRIGS for k, offs in ((10, range(10)), (20, (0, 5, 10, 15)))
                for o in offs]
    starts = [i for i in range(1, R.n) if first <= R.d[i] <= last and R.QL[i] != R.QL[i - 1]]
    table = defaultdict(list)
    for si in starts:
        st = R.d[si]
        E = R.evaluate(st, date(st.year + 2, st.month, min(st.day, 28)), extra=variants)
        hv = E["res"]["hold (the bar)"]["end"]
        for nm, _ in variants:
            table[nm].append(E["res"][nm]["end"] / hv - 1)
    l2 = R.evaluate(R.START, R.END, extra=variants) if park == "afran" else None
    print(f"\n{label}: {len(starts)} windows")
    for name, _ in TRIGS:
        for k, offs in ((10, range(10)), (20, (0, 5, 10, 15))):
            meds = [np.median(table[f"{name}|{k}|{o}"]) * 100 for o in offs]
            beats = [np.mean(np.array(table[f"{name}|{k}|{o}"]) > 0.0005) * 100 for o in offs]
            worst = min(min(table[f"{name}|{k}|{o}"]) for o in offs) * 100
            extra = ""
            if l2:
                hv2 = l2["res"]["hold (the bar)"]["end"]
                xs = [(l2["res"][f"{name}|{k}|{o}"]["end"] / hv2 - 1) * 100 for o in offs]
                extra = f"   last two years {min(xs):+5.1f}% to {max(xs):+5.1f}%"
            print(f"   back early on {name:15} every {k:2} days: median {min(meds):+5.1f}% to {max(meds):+5.1f}%, beat holding in "
                  f"{min(beats):3.0f}-{max(beats):3.0f}% of windows, worst {worst:+6.1f}%" + extra)
