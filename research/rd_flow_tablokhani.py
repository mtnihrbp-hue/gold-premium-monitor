"""The money-flow member rebuilt on tablokhani's recipe (SP-D, 2026-10-05).

tablokhani's public smart-money averages give, for each fund, individuals' 10-day average per-capita
buy and sell and the average daily buyer and seller counts. Rebuilt from TSETMC's daily client types
(research/data/tsetmc_gold_funds.json): for each gold fund, the 10-day means of the daily per-capita
buy (value / buyers) and sell and of the counts; across the funds, per-capita buy weighted by buyers
over per-capita sell weighted by sellers -- buyer power, 10 days. Against the room's original member
(the 20-day mean of the funds' aggregated daily buyer power), inside the room, every 10 days."""
import json
import os
from bisect import bisect_right
from collections import defaultdict
from datetime import date

import numpy as np

import rd_committee_2y as R
import rd_committee_stocks  # noqa: F401
from rd_committee_ablation import make_committee
from rd_committee_veto import BASE
from rd_rebuy import fi_log

HERE = os.path.dirname(os.path.abspath(__file__))
F = json.load(open(os.path.join(HERE, "data", "tsetmc_gold_funds.json"), encoding="utf-8"))


def tablokhani_power():
    per_fund = {}
    for code, f in F.items():
        rows = []
        for x in f["flows"]:
            s = str(x["recDate"])
            k = date(int(s[:4]), int(s[4:6]), int(s[6:]))
            nb, ns = float(x.get("buy_I_Count") or 0), float(x.get("sell_I_Count") or 0)
            vb, vs = float(x.get("buy_I_Value") or 0), float(x.get("sell_I_Value") or 0)
            if nb > 0 and ns > 0:
                rows.append((k, vb / nb, vs / ns, nb, ns))
        rows.sort()
        out = {}
        for j in range(9, len(rows)):
            w = rows[j - 9:j + 1]
            out[rows[j][0]] = (np.mean([r[1] for r in w]), np.mean([r[2] for r in w]), np.mean([r[3] for r in w]),
                               np.mean([r[4] for r in w]))
        per_fund[code] = out
    days = sorted({k for v in per_fund.values() for k in v})
    power = {}
    for k in days:
        b = [v[k] for v in per_fund.values() if k in v]
        nb = sum(x[2] for x in b)
        ns = sum(x[3] for x in b)
        if nb and ns:
            power[k] = (sum(x[0] * x[2] for x in b) / nb) / (sum(x[1] * x[3] for x in b) / ns)
    return power


P = tablokhani_power()
ks = sorted(P)
series = np.array([P[ks[bisect_right(ks, x) - 1]] if bisect_right(ks, x) and (x - ks[bisect_right(ks, x) - 1]).days < 7
                   else np.nan for x in R.d])
R.LEAN["money flow (tablokhani)"] = R.lean_from_z(R.zscore(series), +1)
R.MEMBERS.append("money flow (tablokhani)")
R.PROPOSED["money flow (tablokhani)"] = 0.0
orig, new = np.array(R.LEAN["money flow"]), np.array(R.LEAN["money flow (tablokhani)"])
both = (orig != 0) | (new != 0)
print(f"the two recipes lean the same way on {np.mean(orig[both] == new[both]) * 100:.0f}% of the days either has a view")
TAB = {m: w for m, w in BASE.items() if m != "money flow"}
TAB["money flow (tablokhani)"] = BASE["money flow"]
NOF = {m: w for m, w in BASE.items() if m != "money flow"}


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


V = {"original money flow + stocks": room(BASE, True), "tablokhani money flow + stocks": room(TAB, True),
     "no money flow + stocks": room(NOF, True)}
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
    print(f"\n{label}: {len(starts)} windows")
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
