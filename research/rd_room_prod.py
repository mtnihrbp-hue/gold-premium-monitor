"""The room as production can feed it today (SP-D, 2026-10-05): without the gold funds' money flow
(TSETMC, Iran-only) -- the committee every 10 trading days with the stock index's early return,
against the full room, on every two-year window and offset."""
from collections import defaultdict
from datetime import date

import numpy as np

import rd_committee_2y as R
import rd_committee_stocks  # noqa: F401
from rd_committee_ablation import make_committee
from rd_committee_veto import BASE
from rd_rebuy import fi_log


def room(weights, stocks):
    def outer(k, offset):
        def factory(idx):
            inner = make_committee(dict(weights))(idx)
            held = {"v": False}
            start = idx[0]

            def f(i):
                v = inner(i)
                if (i - start) % k == offset:
                    held["v"] = v
                elif stocks and held["v"] and R.LEAN["stocks 20d"][i] == 1:
                    held["v"] = False
                return held["v"]
            return f
        return factory
    return outer


NOFLOW = {m: w for m, w in BASE.items() if m != "money flow"}
V = {"full room, every 10 days": room(BASE, False), "full room + stocks return": room(BASE, True),
     "no money flow, every 10 days": room(NOFLOW, False), "no money flow + stocks return": room(NOFLOW, True)}
R.AFRAN_LEVEL = R.af_level.copy()
for label, first, last, park in (("Afran windows from 2020", date(2020, 6, 1), date(2024, 10, 5), "afran"),
                                 ("index windows from 2018", date(2018, 1, 1), date(2024, 10, 5), "index")):
    R.af_level = R.AFRAN_LEVEL if park == "afran" else np.exp(np.nan_to_num(fi_log - np.nanmin(fi_log)))
    R.af_ret = np.zeros(R.n)
    R.af_ret[1:] = R.af_level[1:] / R.af_level[:-1] - 1
    ex = [(f"{k}|{o}", f(10, o)) for k, f in V.items() for o in range(10)]
    starts = [i for i in range(1, R.n) if first <= R.d[i] <= last and R.QL[i] != R.QL[i - 1]]
    table = defaultdict(list)
    for si in starts:
        st = R.d[si]
        E = R.evaluate(st, date(st.year + 2, st.month, min(st.day, 28)), extra=ex)
        hv = E["res"]["hold (the bar)"]["end"]
        for nm, _ in ex:
            table[nm].append(E["res"][nm]["end"] / hv - 1)
    last2 = R.evaluate(R.START, R.END, extra=ex) if park == "afran" else None
    print(f"\n{label}: {len(starts)} windows (every offset)")
    for k in V:
        meds = [np.median(table[f"{k}|{o}"]) * 100 for o in range(10)]
        beats = [np.mean(np.array(table[f"{k}|{o}"]) > 0.0005) * 100 for o in range(10)]
        worst = min(min(table[f"{k}|{o}"]) for o in range(10)) * 100
        l2 = ""
        if last2:
            hv2 = last2["res"]["hold (the bar)"]["end"]
            xs = [(last2["res"][f"{k}|{o}"]["end"] / hv2 - 1) * 100 for o in range(10)]
            l2 = f"   last two years {min(xs):+5.1f} to {max(xs):+5.1f}%"
        print(f"   {k:32} median {min(meds):+5.1f} to {max(meds):+5.1f}%, ahead in {min(beats):3.0f}-{max(beats):3.0f}%, worst {worst:+6.1f}%" + l2)
