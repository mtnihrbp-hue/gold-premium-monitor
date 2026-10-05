"""The early return with common sense (SP-D, 2026-10-05). The drafts showed the room selling on a
review day and buying back the next morning because the stock index was already rising. Variants:
  as built      out while the stock index leans to gold -> back the next day
  new turn      back early only when the stock index turns to gold after the sale
  veto + turn   no sale while the stock index leans to gold; back early on a new turn
Every two-year window and offset; round trips shorter than 3 trading days counted."""
from collections import defaultdict
from datetime import date

import numpy as np

import rd_committee_2y as R
import rd_committee_stocks  # noqa: F401
from rd_committee_ablation import make_committee
from rd_committee_veto import BASE
from rd_rebuy import fi_log

NOF = {m: w for m, w in BASE.items() if m != "money flow"}
S = R.LEAN["stocks 20d"]


def variant(kind):
    def outer(k, offset):
        def factory(idx):
            inner = make_committee(dict(NOF))(idx)
            st = {"held": False, "exit_stocks": 0}
            start = idx[0]

            def f(i):
                v = inner(i)
                if (i - start) % k == offset:
                    want = v
                    if kind == "veto + turn" and want and not st["held"] and S[i] == 1:
                        want = False
                    if want and not st["held"]:
                        st["exit_stocks"] = S[i]
                    st["held"] = want
                elif st["held"]:
                    if kind == "as built" and S[i] == 1:
                        st["held"] = False
                    elif kind in ("new turn", "veto + turn"):
                        if S[i] == 1 and st["exit_stocks"] != 1:
                            st["held"] = False
                        st["exit_stocks"] = S[i] if S[i] != 1 else st["exit_stocks"]
                return st["held"]
            return f
        return factory
    return outer


V = {k: variant(k) for k in ("as built", "new turn", "veto + turn")}

def main():
    R.AFRAN_LEVEL = R.af_level.copy()


    def round_trips(fn, idx):
        out = [fn(i) for i in idx]
        quick, start = 0, None
        for k, v in enumerate(out):
            if v and (k == 0 or not out[k - 1]):
                start = k
            if not v and k and out[k - 1] and start is not None and k - start < 3:
                quick += 1
        return quick


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
        print(f"\n{label}: {len(starts)} windows")
        for k in V:
            meds = [np.median(table[f"{k}|{o}"]) * 100 for o in range(10)]
            beats = [np.mean(np.array(table[f"{k}|{o}"]) > 0.0005) * 100 for o in range(10)]
            worst = min(min(table[f"{k}|{o}"]) for o in range(10)) * 100
            line = f"   {k:12} median {min(meds):+5.1f} to {max(meds):+5.1f}%, ahead in {min(beats):3.0f}-{max(beats):3.0f}%, worst {worst:+6.1f}%"
            if park == "afran":
                idx = [i for i in range(R.n) if R.START <= R.d[i] <= R.END]
                E2 = R.evaluate(R.START, R.END, extra=[(k, V[k](10, 0))])
                hv2 = E2["res"]["hold (the bar)"]["end"]
                line += (f" | last two years {(E2['res'][k]['end'] / hv2 - 1) * 100:+5.1f}%, trades {E2['res'][k]['trades']}, "
                         f"round trips under 3 days {round_trips(V[k](10, 0)(idx), idx)}")
            print(line)


if __name__ == "__main__":
    main()
