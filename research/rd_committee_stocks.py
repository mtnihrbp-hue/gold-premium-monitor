"""Does the stock market (TEDPIX) improve the committee? (SP-D, 2026-10-05)

The committee acting every 10 and 20 trading days (rd_committee_cadence2.py), every offset, on the
Afran windows from 2020 and the fixed-income index windows from 2018: with and without a ninth
member, 'stocks 20d' -- TEDPIX's last 20 days, z-scored against its 500 days, +1 (gold) when rising
beyond 0.5, -1 when falling beyond it; weight 1.0."""
import json
import os
from bisect import bisect_right
from collections import defaultdict
from datetime import date

import numpy as np

import rd_committee_2y as R
from rd_committee_cadence2 import every
from rd_rebuy import fi_log

HERE = os.path.dirname(os.path.abspath(__file__))
rows = sorted(json.load(open(os.path.join(HERE, "data", "tedpix.json"))), key=lambda r: r["dEven"])
td = [date(r["dEven"] // 10000, (r["dEven"] // 100) % 100, r["dEven"] % 100) for r in rows]
tv = np.array([r["xNivInuClMresIbs"] for r in rows], dtype=float)
idx = np.array([tv[bisect_right(td, x) - 1] if bisect_right(td, x) else np.nan for x in R.d])
ted20 = np.full(R.n, np.nan)
ted20[20:] = np.log(idx[20:] / idx[:-20])
R.LEAN["stocks 20d"] = R.lean_from_z(R.zscore(ted20), +1)
WITH = dict(R.PROPOSED, **{"stocks 20d": 1.0})
WITHOUT = dict(R.PROPOSED, **{"stocks 20d": 0.0})
R.MEMBERS.append("stocks 20d")
R.PROPOSED["stocks 20d"] = 0.0          # the routines inside evaluate() leave it out

def main():
    R.AFRAN_LEVEL = R.af_level.copy()
    v = R.LEAN["stocks 20d"]
    print(f"stocks 20d leans gold {np.mean(v == 1) * 100:.0f}% / none {np.mean(v == 0) * 100:.0f}% / fixed income {np.mean(v == -1) * 100:.0f}% of days")
    for label, first, last, park in (("Afran windows from 2020", date(2020, 6, 1), date(2024, 10, 5), "afran"),
                                     ("index windows from 2018", date(2018, 1, 1), date(2024, 10, 5), "index")):
        R.af_level = R.AFRAN_LEVEL if park == "afran" else np.exp(np.nan_to_num(fi_log - np.nanmin(fi_log)))
        R.af_ret = np.zeros(R.n)
        R.af_ret[1:] = R.af_level[1:] / R.af_level[:-1] - 1
        variants = [(f"{w}|{k}|{o}", every(k, o, wt)) for w, wt in (("without", WITHOUT), ("with", WITH))
                    for k, offs in ((10, range(10)), (20, (0, 5, 10, 15))) for o in offs]
        starts = [i for i in range(1, R.n) if first <= R.d[i] <= last and R.QL[i] != R.QL[i - 1]]
        table = defaultdict(list)
        for si in starts:
            st = R.d[si]
            E = R.evaluate(st, date(st.year + 2, st.month, min(st.day, 28)), extra=variants)
            hv = E["res"]["hold (the bar)"]["end"]
            for name, _ in variants:
                table[name].append(E["res"][name]["end"] / hv - 1)
        last2 = R.evaluate(R.START, R.END, extra=variants) if park == "afran" else None
        print(f"\n{label}: {len(starts)} windows")
        for w in ("without", "with"):
            for k, offs in ((10, range(10)), (20, (0, 5, 10, 15))):
                meds = [np.median(table[f"{w}|{k}|{o}"]) * 100 for o in offs]
                beats = [np.mean(np.array(table[f"{w}|{k}|{o}"]) > 0.0005) * 100 for o in offs]
                worst = min(min(table[f"{w}|{k}|{o}"]) for o in offs) * 100
                l2 = ""
                if last2:
                    hv2 = last2["res"]["hold (the bar)"]["end"]
                    l2s = [(last2["res"][f"{w}|{k}|{o}"]["end"] / hv2 - 1) * 100 for o in offs]
                    l2 = f"   last two years {min(l2s):+5.1f}% to {max(l2s):+5.1f}%"
                print(f"   {w:7} the stock member, every {k:2} days: median {min(meds):+5.1f}% to {max(meds):+5.1f}%, beat holding "
                      f"in {min(beats):3.0f}-{max(beats):3.0f}% of windows, worst {worst:+6.1f}%" + l2)


if __name__ == "__main__":
    main()
