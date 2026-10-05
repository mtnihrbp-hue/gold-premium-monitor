"""The volume profile as a committee member (SP-D, 2026-10-05).

rd_fund_intraday.py: Ayyar's close against the 20-session value area of its minute volume led 18K
(+0.19 over 20 days, luck 2%; gold over fixed income over 60 days +0.19, luck 0%). Minute bars
start in 2023-10, too late for the two-year windows, so the same measure is built from daily data
back to 2017: each day's value traded spread evenly over its low..high (caluclator/technical's
volume_profile idea), Ayyar alone and all gold funds summed. First the two versions are compared
where both exist; then the daily version joins the committee as 'volume profile' (+1 gold when the
close is above the 20-day POC by more than its usual, -1 below), tested every 10 / 20 days."""
import json
import os
from collections import defaultdict
from datetime import date

import numpy as np

import rd_committee_2y as R
from rd_committee_cadence2 import every
from rd_rebuy import fi_log

HERE = os.path.dirname(os.path.abspath(__file__))
F = json.load(open(os.path.join(HERE, "data", "tsetmc_gold_funds.json"), encoding="utf-8"))
AYAR = "34144395039913458"


def daily_gap(prices, window=20, bin_pct=0.25):
    """close against the window's POC (%), from daily high/low/value."""
    p = sorted((x for x in prices if x["low"] > 0 and x["high"] >= x["low"] and x["value"] > 0), key=lambda x: x["date"])
    out = {}
    for j in range(window, len(p)):
        w = p[j - window:j + 1]
        lo = min(x["low"] for x in w)
        hi = max(x["high"] for x in w)
        step = np.log1p(bin_pct / 100)
        edges = np.arange(np.log(lo), np.log(hi) + step, step)
        if len(edges) < 3:
            continue
        mass = np.zeros(len(edges) - 1)
        for x in w:
            if x["low"] <= 0 or x["value"] <= 0:
                continue
            a = int(np.clip(np.searchsorted(edges, np.log(x["low"])) - 1, 0, len(mass) - 1))
            b = int(np.clip(np.searchsorted(edges, np.log(x["high"])) - 1, a, len(mass) - 1))
            mass[a:b + 1] += x["value"] / (b - a + 1)
        poc = np.exp((edges[np.argmax(mass)] + edges[np.argmax(mass) + 1]) / 2)
        k = p[j]["date"]
        out[date(int(k[:4]), int(k[4:6]), int(k[6:]))] = (p[j]["close"] / poc - 1) * 100
    return out


ayar_daily = daily_gap(F[AYAR]["prices"])
# the minute-based gap for the same days
import rd_fund_intraday as M  # noqa: E402  (runs its own report on import is avoided below)
minute = {r["date"]: r.get("va20_gap") for r in M.rows if r.get("va20_gap") is not None}
both = [k for k in minute if k in ayar_daily]
a = np.array([minute[k] for k in both])
b = np.array([ayar_daily[k] for k in both])
print(f"Ayyar, close against its 20-day POC: minute-based against daily-based, {len(both)} common days: correlation "
      f"{np.corrcoef(a, b)[0, 1]:+.2f}, same sign on {np.mean(np.sign(a) == np.sign(b)) * 100:.0f}% of days")

# all gold funds summed: each fund's gap weighted by its value traded
agg_w, agg_v = defaultdict(float), defaultdict(float)
for code, f in F.items():
    g = daily_gap(f["prices"])
    val = {date(int(x["date"][:4]), int(x["date"][4:6]), int(x["date"][6:])): x["value"] for x in f["prices"]}
    for k, v in g.items():
        agg_w[k] += v * val.get(k, 0)
        agg_v[k] += val.get(k, 0)
allfunds = {k: agg_w[k] / agg_v[k] for k in agg_v if agg_v[k] > 0}
print(f"all gold funds: {len(allfunds)} days, {min(allfunds)} -> {max(allfunds)}")

gap = np.full(R.n, np.nan)
for k, v in allfunds.items():
    i = {x: j for j, x in enumerate(R.d)}.get(k)
    if i is not None:
        gap[i] = v
for i in range(1, R.n):                    # carry over non-exchange days (at most 3)
    if not np.isfinite(gap[i]) and np.isfinite(gap[i - 1]) and (i < 3 or np.isfinite(gap[i - 3:i]).any()):
        gap[i] = gap[i - 1]
R.LEAN["volume profile"] = R.lean_from_z(R.zscore(gap), +1)
R.MEMBERS.append("volume profile")
R.PROPOSED["volume profile"] = 0.0
WITHOUT = dict(R.PROPOSED)
WITH = dict(R.PROPOSED, **{"volume profile": 1.0})
v = R.LEAN["volume profile"]
print(f"volume profile leans gold {np.mean(v == 1) * 100:.0f}% / none {np.mean(v == 0) * 100:.0f}% / fixed income "
      f"{np.mean(v == -1) * 100:.0f}% of days")

def main():
    R.AFRAN_LEVEL = R.af_level.copy()
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
        print(f"\n{label}: {len(starts)} windows")
        for w in ("without", "with"):
            for k, offs in ((10, range(10)), (20, (0, 5, 10, 15))):
                meds = [np.median(table[f"{w}|{k}|{o}"]) * 100 for o in offs]
                beats = [np.mean(np.array(table[f"{w}|{k}|{o}"]) > 0.0005) * 100 for o in offs]
                worst = min(min(table[f"{w}|{k}|{o}"]) for o in offs) * 100
                print(f"   {w:7} the volume profile, every {k:2} days: median {min(meds):+5.1f}% to {max(meds):+5.1f}%, beat "
                      f"holding in {min(beats):3.0f}-{max(beats):3.0f}% of windows, worst {worst:+6.1f}%")


if __name__ == "__main__":
    main()
