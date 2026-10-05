"""The cadence result under harder tests (SP-D, 2026-10-05).

1. Equal weights against the proposed ones (chosen with hindsight in section 18).
2. Windows from 2018 (the currency storm) with the fixed-income index as the parking asset
   (Afran starts in 2020), against the Afran windows from 2020.
Every cadence is run at every offset; the table gives, across offsets, the range of the median
gain over holding and of the share of windows that beat holding."""
from collections import defaultdict
from datetime import date

import numpy as np

import rd_committee_2y as R
from rd_committee_ablation import make_committee
from rd_rebuy import fi_log


def every(k, offset, weights):
    def factory(idx):
        inner = make_committee(dict(weights))(idx)
        held = {"v": False}
        start = idx[0]

        def f(i):
            v = inner(i)
            if (i - start) % k == offset:
                held["v"] = v
            return held["v"]
        return f
    return factory


EQUAL = {m: 1.0 for m in R.MEMBERS}
CADENCES = ((1, (0,)), (5, range(5)), (10, range(10)), (20, (0, 5, 10, 15)))


def run(first, last, park):
    if park == "index":
        R.af_level = np.exp(np.nan_to_num(fi_log - np.nanmin(fi_log)))
    else:
        R.af_level = R.AFRAN_LEVEL
    R.af_ret = np.zeros(R.n)
    R.af_ret[1:] = R.af_level[1:] / R.af_level[:-1] - 1
    variants = [(f"{wname}|{k}|{o}", every(k, o, w)) for wname, w in (("proposed", R.PROPOSED), ("equal", EQUAL))
                for k, offs in CADENCES for o in offs]
    starts = [i for i in range(1, R.n) if first <= R.d[i] <= last and R.QL[i] != R.QL[i - 1]]
    table = defaultdict(list)
    for si in starts:
        st = R.d[si]
        E = R.evaluate(st, date(st.year + 2, st.month, min(st.day, 28)), extra=variants)
        hv = E["res"]["hold (the bar)"]["end"]
        for name, _ in variants:
            table[name].append(E["res"][name]["end"] / hv - 1)
    return table, len(starts)


# 3. leave on the schedule, come back at once: the expensive mistake is to be out at a jump
def leave_slow(k, offset, weights):
    def factory(idx):
        inner = make_committee(dict(weights))(idx)
        held = {"v": False}
        start = idx[0]

        def f(i):
            v = inner(i)
            if (i - start) % k == offset:
                held["v"] = v
            elif held["v"] and not v:
                held["v"] = False            # the consensus broke: back to gold the same day
            return held["v"]
        return f
    return factory



def main():
    R.AFRAN_LEVEL = R.af_level.copy()
    for label, first, last, park in (("Afran, windows from 1399 Q2 (2020)", date(2020, 6, 1), date(2024, 10, 5), "afran"),
                                     ("fixed-income index, windows from 1396 Q4 (2018)", date(2018, 1, 1), date(2024, 10, 5), "index")):
        table, nw = run(first, last, park)
        print(f"\n{label}: {nw} two-year windows")
        print("   weights    cadence     median gain over holding (range over offsets)   windows beating holding   worst window")
        for wname in ("proposed", "equal"):
            for k, offs in CADENCES:
                meds = [np.median(table[f"{wname}|{k}|{o}"]) * 100 for o in offs]
                beats = [np.mean(np.array(table[f"{wname}|{k}|{o}"]) > 0.0005) * 100 for o in offs]
                worst = min(min(table[f"{wname}|{k}|{o}"]) for o in offs) * 100
                print(f"   {wname:9}  every {k:2} d   {min(meds):+6.1f}% to {max(meds):+6.1f}%                         "
                      f"{min(beats):4.0f}% to {max(beats):4.0f}%          {worst:+6.1f}%")




    for label, first, last, park in (("Afran, windows from 1399 Q2 (2020)", date(2020, 6, 1), date(2024, 10, 5), "afran"),
                                     ("fixed-income index, windows from 1396 Q4 (2018)", date(2018, 1, 1), date(2024, 10, 5), "index")):
        if park == "index":
            R.af_level = np.exp(np.nan_to_num(fi_log - np.nanmin(fi_log)))
        else:
            R.af_level = R.AFRAN_LEVEL
        R.af_ret = np.zeros(R.n)
        R.af_ret[1:] = R.af_level[1:] / R.af_level[:-1] - 1
        variants = [(f"{wname}|{k}|{o}", leave_slow(k, o, w)) for wname, w in (("proposed", R.PROPOSED), ("equal", EQUAL))
                    for k, offs in ((10, range(10)), (20, (0, 5, 10, 15))) for o in offs]
        starts = [i for i in range(1, R.n) if first <= R.d[i] <= last and R.QL[i] != R.QL[i - 1]]
        table = defaultdict(list)
        for si in starts:
            st = R.d[si]
            E = R.evaluate(st, date(st.year + 2, st.month, min(st.day, 28)), extra=variants)
            hv = E["res"]["hold (the bar)"]["end"]
            for name, _ in variants:
                table[name].append(E["res"][name]["end"] / hv - 1)
        print(f"\nLEAVE ON THE SCHEDULE, BACK AT ONCE -- {label}: {len(starts)} windows")
        for wname in ("proposed", "equal"):
            for k, offs in ((10, range(10)), (20, (0, 5, 10, 15))):
                meds = [np.median(table[f"{wname}|{k}|{o}"]) * 100 for o in offs]
                beats = [np.mean(np.array(table[f"{wname}|{k}|{o}"]) > 0.0005) * 100 for o in offs]
                worst = min(min(table[f"{wname}|{k}|{o}"]) for o in offs) * 100
                print(f"   {wname:9}  every {k:2} d   {min(meds):+6.1f}% to {max(meds):+6.1f}%                         "
                      f"{min(beats):4.0f}% to {max(beats):4.0f}%          {worst:+6.1f}%")


if __name__ == "__main__":
    main()
