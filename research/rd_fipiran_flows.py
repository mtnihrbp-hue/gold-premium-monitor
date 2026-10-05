"""Real money into the gold ETFs, their premium, and money into fixed income, from fipiran (SP-D, 2026-10-05).

Data: research/data/fipiran_funds.json (fetch_fipiran.py): every commodity (gold) and fixed-income fund's
daily redemption NAV, net assets and units outstanding, 2019 -> 2026-10. The gold funds are those whose
TSETMC code is in research/data/tsetmc_gold_funds.json.

  inflow           the gold funds' net creations: the change in units outstanding x the redemption NAV,
                   summed over the funds, as a share of their net assets (% a day); and over 5 and 20 days
  premium          the funds' exchange close (TSETMC) against their redemption NAV, weighted by net assets
  safety           the same net creations for the fixed-income funds, % of their net assets, 20 days
  gold vs safety   the gold funds' 20-day inflow minus the fixed-income funds'

Against 18K's next 5 and 20 days (from the next day's close: fipiran's NAV is published after the day) and
gold over fixed income over 60 days, after 18K's own last 5 and 20 days, circular-shift luck; then as
committee members (rd_committee_2y.py's room, every 10 / 20 trading days, every offset).
"""
import json
import os
from collections import defaultdict
from datetime import date

import numpy as np
from scipy.stats import rankdata

from rd_rebuy import X60, c, d, n

HERE = os.path.dirname(os.path.abspath(__file__))
FP = json.load(open(os.path.join(HERE, "data", "fipiran_funds.json"), encoding="utf-8"))
TS = json.load(open(os.path.join(HERE, "data", "tsetmc_gold_funds.json"), encoding="utf-8"))
GOLD_CODES = set(TS)
close_by = {code: {date(int(p["date"][:4]), int(p["date"][4:6]), int(p["date"][6:])): p["close"] for p in f["prices"]}
            for code, f in TS.items()}
gix = {x: i for i, x in enumerate(d)}

days = sorted(date.fromisoformat(k) for k, v in FP.items() if v)
units, nav, assets = defaultdict(dict), defaultdict(dict), defaultdict(dict)
ftype = {}
for k in days:
    for r in FP[k.isoformat()]:
        key = r.get("insCode") or r["regNo"]
        if not r.get("investedUnits") or not r.get("cancelNav"):
            continue
        units[key][k], nav[key][k], assets[key][k] = r["investedUnits"], r["cancelNav"], r.get("netAsset") or 0
        ftype[key] = "gold" if str(r.get("insCode")) in GOLD_CODES else ("fi" if r["fundType"] == 4 else "other")

NAVH = json.load(open(os.path.join(HERE, "data", "fipiran_nav.json"), encoding="utf-8"))


def window_flow(kind, lag_days):
    """At each sample date: net creations over the last `lag_days` (units now - units then, at today's
    redemption NAV), summed over the funds of `kind`, as % of their net assets then."""
    out = {}
    for k in days:
        num = den = 0.0
        for key, u in units.items():
            if ftype[key] != kind or k not in u:
                continue
            earlier = [x for x in u if lag_days - 3 <= (k - x).days <= lag_days + 3]
            if not earlier:
                continue
            a = min(earlier, key=lambda x: abs((k - x).days - lag_days))
            num += (u[k] - u[a]) * nav[key][k]
            den += assets[key][a] or u[a] * nav[key][a]
        if den > 0:
            out[k] = num / den * 100
    return out


def carried(dct, max_gap=9):
    """Daily series from sample dates: each value known from its date for up to `max_gap` days."""
    out = np.full(n, np.nan)
    ks = sorted(dct)
    j = 0
    for i, x in enumerate(d):
        while j + 1 < len(ks) and ks[j + 1] <= x:
            j += 1
        if ks and ks[j] <= x and (x - ks[j]).days <= max_gap:
            out[i] = dct[ks[j]]
    return out


# daily premium: each gold fund's NAV rebuilt from its daily NAV returns, anchored to fipiran's reported
# redemption NAV (the median ratio over the sample dates), against its TSETMC close
prem_w, prem_v = defaultdict(float), defaultdict(float)
for reg, h in NAVH.items():
    key = h.get("insCode")
    items = sorted(h["items"], key=lambda x: x["date"])
    if not items or str(key) not in close_by:
        continue
    level, lvl = 1.0, {}
    for it in items:
        level *= 1 + (it["daily"] or 0) / 100
        lvl[date.fromisoformat(it["date"])] = level
    rep = nav.get(key, {})
    ratios = [rep[k] / lvl[k] for k in rep if k in lvl and lvl[k] > 0]
    if not ratios:
        continue
    scale = float(np.median(ratios))
    cl = close_by[str(key)]
    size = assets.get(key, {})
    for k, v in lvl.items():
        if k in cl and cl[k] > 0:
            w = size[max((x for x in size if x <= k), default=min(size))] if size else 1.0
            prem_w[k] += (cl[k] / (v * scale) - 1) * 100 * w
            prem_v[k] += w

premium = np.full(n, np.nan)
for k in prem_v:
    i = gix.get(k)
    if i is not None and prem_v[k] > 0:
        premium[i] = prem_w[k] / prem_v[k]
g7, g28 = window_flow("gold", 7), window_flow("gold", 28)
f28 = window_flow("fi", 28)
SIG = {"gold inflow, 7 days": carried(g7), "gold inflow, 28 days": carried(g28), "premium": premium,
       "premium's 5-day change": np.concatenate([np.full(5, np.nan), premium[5:] - premium[:-5]]),
       "fixed-income inflow, 28 days": carried(f28)}
SIG["gold vs safety, 28 days"] = SIG["gold inflow, 28 days"] - SIG["fixed-income inflow, 28 days"]
gold_in = SIG["gold inflow, 7 days"]


def fwd(h):
    out = np.full(n, np.nan)
    out[:n - 1 - h] = (c[1 + h:] / c[1:n - h] - 1) * 100
    return out


def back(k):
    out = np.full(n, np.nan)
    out[k:] = (c[k:] / c[:-k] - 1) * 100
    return out


def report():
    print(f"fipiran: {len(days)} days, {days[0]} -> {days[-1]}; gold funds {sum(1 for t in ftype.values() if t == 'gold')}, "
          f"fixed income {sum(1 for t in ftype.values() if t == 'fi')}")
    for y in range(2019, 2027):
        sel = [i for i in range(n) if d[i].year == y]
        gi = [g28[k] for k in g28 if k.year == y]
        pr = premium[sel]
        if gi:
            gi = np.array(gi)
            print(f"   {y}: gold funds' 28-day net inflow, median {np.median(gi):+5.1f}% of assets; premium median "
                  f"{np.nanmedian(pr):+5.2f}% (5-95%: {np.nanpercentile(pr, 5):+.2f} to {np.nanpercentile(pr, 95):+.2f})"
                  if np.isfinite(pr).any() else f"   {y}: gold inflow {np.nansum(gi):+6.1f}%")
    Y = {"18K 5d": fwd(5), "18K 20d": fwd(20), "gold-FI 60d": X60}
    CT = [back(5), back(20)]
    rng = np.random.default_rng(37)
    print("\nrank correlation after 18K's own last 5 and 20 days (luck)")
    for label, lo, hi in (("2019-2022", date(2019, 1, 1), date(2022, 12, 31)), ("2023-2026", date(2023, 1, 1), date(2026, 12, 31))):
        sel = np.array([lo <= x <= hi for x in d])
        for name, s in SIG.items():
            cells = []
            for t, y in Y.items():
                ok = sel & np.isfinite(s) & np.isfinite(y) & np.isfinite(CT[0]) & np.isfinite(CT[1])
                m = ok.sum()
                if m < 120:
                    cells.append(f"{t} -")
                    continue
                X = np.column_stack([np.ones(m)] + [rankdata(x[ok]) / m for x in CT])
                res = lambda v: v - X @ np.linalg.lstsq(X, v, rcond=None)[0]
                a, b = res(rankdata(s[ok]) / m), res(rankdata(y[ok]) / m)
                v = np.corrcoef(a, b)[0, 1]
                null = [np.corrcoef(np.roll(a, rng.integers(30, m - 30)), b)[0, 1] for _ in range(300)]
                cells.append(f"{t} {v:+.2f} ({np.mean(np.abs(null) >= abs(v)) * 100:2.0f}%)")
            print(f"   {label} {name:30} " + "  ".join(cells))


def room():
    """The three readings as committee members, their directions fixed in advance (economic priors,
    not the results): a high premium leans fixed income (hot money crowding in); strong net creations
    into the gold funds lean fixed income (retail chasing); strong net creations into the fixed-income
    funds lean gold (fear, which in toman has come before gold's next move). Weight 1 each; the room
    every 10 / 20 days, every offset; and the fixed-income inflow as the early return instead."""
    from collections import defaultdict as dd

    import rd_committee_2y as R
    from rd_committee_cadence2 import every
    from rd_committee_reentry import reentry
    from rd_rebuy import fi_log
    import rd_committee_stocks  # noqa: F401
    R.LEAN["premium"] = R.lean_from_z(R.zscore(SIG["premium"], 250), -1)
    R.LEAN["gold inflow"] = R.lean_from_z(R.zscore(SIG["gold inflow, 28 days"], 250), -1)
    R.LEAN["safety inflow"] = R.lean_from_z(R.zscore(SIG["fixed-income inflow, 28 days"], 250), +1)
    for m in ("premium", "gold inflow", "safety inflow"):
        R.MEMBERS.append(m)
        R.PROPOSED[m] = 0.0
    base = {m: w for m, w in R.PROPOSED.items() if w > 0}
    variants = {"the room as it is": base}
    for m in ("premium", "gold inflow", "safety inflow"):
        variants[f"+ {m}"] = dict(base, **{m: 1.0})
    variants["+ all three"] = dict(base, **{"premium": 1.0, "gold inflow": 1.0, "safety inflow": 1.0})
    R.AFRAN_LEVEL = R.af_level.copy()
    first = next(x for x in d if np.isfinite(R.LEAN["premium"][gix[x]]) and x >= date(2020, 6, 1))
    starts = [i for i in range(1, n) if date(2021, 6, 1) <= d[i] <= date(2024, 10, 5) and R.QL[i] != R.QL[i - 1]]
    ex = [(f"{k}|{c_}|{o}", every(c_, o, w)) for k, w in variants.items() for c_, offs in ((10, range(10)), (20, (0, 5, 10, 15)))
          for o in offs]
    ex += [(f"back early on safety inflow|10|{o}", reentry(10, o, ("safety inflow",))) for o in range(10)]
    table = dd(list)
    for si in starts:
        st = d[si]
        E = R.evaluate(st, date(st.year + 2, st.month, min(st.day, 28)), extra=ex)
        hv = E["res"]["hold (the bar)"]["end"]
        for nm, _ in ex:
            table[nm].append(E["res"][nm]["end"] / hv - 1)
    print(f"\nIN THE ROOM: {len(starts)} two-year windows (Afran), starting 1400 Q1 -> 1403 Q3")
    for k in list(variants) + ["back early on safety inflow"]:
        for c_, offs in ((10, range(10)), (20, (0, 5, 10, 15))):
            if k.startswith("back") and c_ == 20:
                continue
            meds = [np.median(table[f"{k}|{c_}|{o}"]) * 100 for o in offs]
            beats = [np.mean(np.array(table[f"{k}|{c_}|{o}"]) > 0.0005) * 100 for o in offs]
            worst = min(min(table[f"{k}|{c_}|{o}"]) for o in offs) * 100
            print(f"   {k:30} every {c_:2} days: median {min(meds):+5.1f}% to {max(meds):+5.1f}%, beat holding in "
                  f"{min(beats):3.0f}-{max(beats):3.0f}% of windows, worst {worst:+6.1f}%")


if __name__ == "__main__":
    report()
    room()
