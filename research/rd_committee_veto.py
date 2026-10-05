"""Momentum signals as a veto on leaving gold, not as voters (SP-D, 2026-10-05).

The volume profile (the gold funds' close against their 20-session POC) and the stock index both lead
18K, yet as voters they lowered the committee's result (rd_vp_member.py, rd_committee_stocks.py):
their votes for fixed income fall in dips that recover. Here they may only block an exit: the
committee (proposed weights, its view moving daily, acted on every 10 / 20 days) leaves gold only
if the veto member is not leaning to gold that day."""
from collections import defaultdict
from datetime import date

import numpy as np

import rd_committee_2y as R
import rd_committee_stocks  # noqa: F401  (adds 'stocks 20d' to R.LEAN, weight 0 in PROPOSED)
import rd_vp_member  # noqa: F401  (adds 'volume profile', weight 0 in PROPOSED)
from rd_committee_ablation import make_committee
from rd_rebuy import fi_log

BASE = {m: w for m, w in R.PROPOSED.items() if m not in ("stocks 20d", "volume profile")}


def vetoed(k, offset, veto):
    def factory(idx):
        inner = make_committee(dict(BASE))(idx)
        held = {"v": False}
        start = idx[0]

        def f(i):
            v = inner(i)
            if (i - start) % k == offset:
                blocked = any(R.LEAN[m][i] == 1 for m in veto)
                held["v"] = v and not (blocked and not held["v"])   # a veto stops a new exit, not a held one
            return held["v"]
        return f
    return factory


VETOS = (("no veto", ()), ("volume profile veto", ("volume profile",)), ("stocks veto", ("stocks 20d",)),
         ("both as vetoes", ("volume profile", "stocks 20d")))

def main():
    R.AFRAN_LEVEL = R.af_level.copy()
    for label, first, last, park in (("Afran windows from 2020", date(2020, 6, 1), date(2024, 10, 5), "afran"),
                                     ("index windows from 2018", date(2018, 1, 1), date(2024, 10, 5), "index")):
        R.af_level = R.AFRAN_LEVEL if park == "afran" else np.exp(np.nan_to_num(fi_log - np.nanmin(fi_log)))
        R.af_ret = np.zeros(R.n)
        R.af_ret[1:] = R.af_level[1:] / R.af_level[:-1] - 1
        variants = [(f"{name}|{k}|{o}", vetoed(k, o, vs)) for name, vs in VETOS for k, offs in ((10, range(10)), (20, (0, 5, 10, 15)))
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
        for name, _ in VETOS:
            for k, offs in ((10, range(10)), (20, (0, 5, 10, 15))):
                meds = [np.median(table[f"{name}|{k}|{o}"]) * 100 for o in offs]
                beats = [np.mean(np.array(table[f"{name}|{k}|{o}"]) > 0.0005) * 100 for o in offs]
                worst = min(min(table[f"{name}|{k}|{o}"]) for o in offs) * 100
                extra = ""
                if l2:
                    hv2 = l2["res"]["hold (the bar)"]["end"]
                    xs = [(l2["res"][f"{name}|{k}|{o}"]["end"] / hv2 - 1) * 100 for o in offs]
                    extra = f"   last two years {min(xs):+5.1f}% to {max(xs):+5.1f}%"
                print(f"   {name:20} every {k:2} days: median {min(meds):+5.1f}% to {max(meds):+5.1f}%, beat holding in "
                      f"{min(beats):3.0f}-{max(beats):3.0f}% of windows, worst {worst:+6.1f}%" + extra)


if __name__ == "__main__":
    main()
