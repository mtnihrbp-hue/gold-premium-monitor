"""The room at Goldika's cost instead of Daric's (SP-D, 2026-10-05): Daric refuses GitHub's runner, so
PAPER trades on Goldika (2.37% between its buy and sell) until the Iran-side collector."""
from collections import defaultdict
from datetime import date

import numpy as np

import rd_committee_2y as R
from rd_room_reentry_sense import variant

R.AFRAN_LEVEL = R.af_level.copy()
for cost in (0.30, 1.0, 2.37):
    R.GOLD_HALF = cost / 200
    starts = [i for i in range(1, R.n) if date(2020, 6, 1) <= R.d[i] <= date(2024, 10, 5) and R.QL[i] != R.QL[i - 1]]
    ex = [(f"room|{o}", variant("veto + turn")(10, o)) for o in range(10)]
    table = defaultdict(list)
    for si in starts:
        st = R.d[si]
        E = R.evaluate(st, date(st.year + 2, st.month, min(st.day, 28)), extra=ex)
        hv = E["res"]["hold (the bar)"]["end"]
        for nm, _ in ex:
            table[nm].append(E["res"][nm]["end"] / hv - 1)
    meds = [np.median(table[f"room|{o}"]) * 100 for o in range(10)]
    beats = [np.mean(np.array(table[f"room|{o}"]) > 0.0005) * 100 for o in range(10)]
    worst = min(min(table[f"room|{o}"]) for o in range(10)) * 100
    E2 = R.evaluate(R.START, R.END, extra=[("room", variant("veto + turn")(10, 0))])
    l2 = (E2["res"]["room"]["end"] / E2["res"]["hold (the bar)"]["end"] - 1) * 100
    print(f"round trip {cost:4.2f}%: median {min(meds):+5.1f} to {max(meds):+5.1f}%, ahead in {min(beats):3.0f}-{max(beats):3.0f}%,"
          f" worst {worst:+5.1f}%, last two years {l2:+5.1f}%")
