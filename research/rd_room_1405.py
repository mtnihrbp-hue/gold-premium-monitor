"""What the room did through the 1405 channel and the jump, day by day (SP-D, 2026-10-05).

The committee (proposed weights, its view moving daily, acted on every 10 trading days, offset 0 from
the two-year window's start 1403/07/14), with and without the early return to gold when the stock
index rises (rd_committee_reentry.py). Every switch, the grams moved, and the result against holding
over 1404/11/01 -> 1405/07/09."""
from datetime import date

import numpy as np

import rd_committee_2y as R
from rd_committee_cadence2 import every
from rd_committee_reentry import reentry
import rd_committee_stocks  # noqa: F401
from rd_committee_veto import BASE

E = R.evaluate(R.START, R.END, extra=[("room every 10 days", every(10, 0, BASE)),
                                      ("room + back early on stocks", reentry(10, 0, ("stocks 20d",)))])
idx = E["idx"]
pos = {i: k for k, i in enumerate(idx)}
for name in ("room every 10 days", "room + back early on stocks"):
    fac = dict([("room every 10 days", every(10, 0, BASE)), ("room + back early on stocks", reentry(10, 0, ("stocks 20d",)))])[name]
    f = fac(idx)
    states = [f(i) for i in idx]
    print(f"\n{name}:")
    prev = False
    for i, s in zip(idx, states):
        if s != prev and R.d[i] >= date(2025, 10, 1):
            mk = {m: int(R.LEAN[m][i]) for m in R.MEMBERS if m in BASE}
            against = [m for m, v in mk.items() if v == -1]
            print(f"   {R.rows[i]['jdate']} 18K {R.c[i] / 1e7:5.2f}M  -> {'40% to fixed income' if s else 'back to gold'}"
                  + (f"   (for fixed income: {', '.join(against)})" if s else ""))
        prev = s
    v = E["res"][name]["values"]
    hv = E["res"]["hold (the bar)"]["values"]
    a = pos[next(i for i in idx if R.d[i] >= date(2026, 1, 21))]
    print(f"   1404/11/01 -> 1405/07/09: {(v[-1] / v[a] - 1) * 100:+.1f}% against holding's {(hv[-1] / hv[a] - 1) * 100:+.1f}%;"
          f" the two years {(E['res'][name]['end'] / E['res']['hold (the bar)']['end'] - 1) * 100:+.1f}% against holding")
