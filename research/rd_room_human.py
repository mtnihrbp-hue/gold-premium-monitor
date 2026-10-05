"""The owner's room, with common sense: the phase first, then the action (SP-D, 2026-10-05).

The owner: "the room should have common sense, like a human. If the trend is bullish, all out to
gold; if sideways, it should be able to extrapolate and sell some gold into fixed income and keep
the rest, and keep a sharp eye to rebuy the sold gold back."

The phase is the chartist's (research/chartist.py), as known each day:
  bull       MARKUP                               -> all the grams in gold
  sideways   ACCUMULATION or DISTRIBUTION         -> keep 60%; the 40% swing goes to fixed income when
                                                     the price is in the upper part of the box (at or
                                                     over 60% of its height), and is bought back when
                                                     the price is back in its lower part (30% or less),
                                                     when the box breaks upward, or when the stock
                                                     index rises (the early return of section 24)
  downtrend  MARKDOWN                             -> two variants: hold everything (the owner did not
                                                     say), or the swing to fixed income until the phase
                                                     changes
  between    TRANSITION                           -> the posture stays
Acted on daily, the owner's contract (rd_committee_2y.py). Scored by phase: over the days of each
phase, the room's return against holding's -- where it earns and where it pays -- and over every
two-year window.
"""
from collections import defaultdict
from datetime import date

import numpy as np

import rd_committee_2y as R
import rd_committee_stocks  # noqa: F401  (R.LEAN["stocks 20d"])
from rd_committee_cadence2 import every
from rd_committee_veto import BASE
from rd_rebuy import fi_log

PHASE = np.empty(R.n, dtype=object)
POS = np.full(R.n, np.nan)
for i in range(next(k for k in range(R.n) if R.d[k] >= date(2015, 1, 1)), R.n):
    r = R.chart.read(i)
    PHASE[i] = r["phase"]
    if r.get("box"):
        lo, hi = r["box"]
        POS[i] = (R.c[i] - lo) / (hi - lo) if hi > lo else 0.5
BULL, SIDE, BEAR = "MARKUP", ("ACCUMULATION", "DISTRIBUTION"), "MARKDOWN"


def human(bear_out, stocks_return=True):
    def factory(idx):
        s = {"out": False}

        def f(i):
            ph = PHASE[i]
            if ph == BULL:
                s["out"] = False
            elif ph in SIDE:
                if not s["out"] and np.isfinite(POS[i]) and POS[i] >= 0.6:
                    s["out"] = True
                elif s["out"] and ((np.isfinite(POS[i]) and POS[i] <= 0.3) or POS[i] > 1.0
                                   or (stocks_return and R.LEAN["stocks 20d"][i] == 1)):
                    s["out"] = False
            elif ph == BEAR:
                s["out"] = bool(bear_out) and not (stocks_return and R.LEAN["stocks 20d"][i] == 1)
            return s["out"]
        return f
    return factory


VARIANTS = [("owner's room, downtrend held", human(False)), ("owner's room, downtrend out", human(True)),
            ("owner's room, no stock return", human(True, stocks_return=False)),
            ("the committee, every 10 days", every(10, 0, BASE))]


def by_phase(E, name, idx):
    v, hv = E["res"][name]["values"], E["res"]["hold (the bar)"]["values"]
    out = defaultdict(float)
    days = defaultdict(int)
    for k in range(1, len(idx)):
        ph = PHASE[idx[k - 1]] or "-"
        ph = "sideways" if ph in SIDE else {"MARKUP": "bull", "MARKDOWN": "downtrend", "TRANSITION": "between"}.get(ph, ph)
        out[ph] += (np.log(v[k] / v[k - 1]) - np.log(hv[k] / hv[k - 1])) * 100
        days[ph] += 1
    return out, days


R.AFRAN_LEVEL = R.af_level.copy()
for label, lo, hi, park in (("2016-2023, fixed-income index", date(2016, 1, 1), date(2023, 12, 31), "index"),
                            ("2024-2026, Afran", date(2024, 1, 1), date(2026, 10, 1), "afran"),
                            ("the last two years", R.START, R.END, "afran")):
    R.af_level = R.AFRAN_LEVEL if park == "afran" else np.exp(np.nan_to_num(fi_log - np.nanmin(fi_log)))
    R.af_ret = np.zeros(R.n)
    R.af_ret[1:] = R.af_level[1:] / R.af_level[:-1] - 1
    E = R.evaluate(lo, hi, extra=VARIANTS)
    idx = E["idx"]
    hold = E["res"]["hold (the bar)"]["end"]
    _, days = by_phase(E, "hold (the bar)", idx)
    print(f"\n{label}: hold x{hold / 1.35e9:.2f};  days by phase: " + ", ".join(f"{k} {v}" for k, v in sorted(days.items())))
    for name, _ in VARIANTS:
        rs = E["res"][name]
        ph, _ = by_phase(E, name, idx)
        print(f"   {name:32} {(rs['end'] / hold - 1) * 100:+6.1f}% against holding, {rs['trades']:3} trades;  by phase (points): "
              + ", ".join(f"{k} {v:+.1f}" for k, v in sorted(ph.items())))

R.af_level = R.AFRAN_LEVEL
R.af_ret = np.zeros(R.n)
R.af_ret[1:] = R.af_level[1:] / R.af_level[:-1] - 1
starts = [i for i in range(1, R.n) if date(2020, 6, 1) <= R.d[i] <= date(2024, 10, 5) and R.QL[i] != R.QL[i - 1]]
table = defaultdict(list)
for si in starts:
    st = R.d[si]
    E = R.evaluate(st, date(st.year + 2, st.month, min(st.day, 28)), extra=VARIANTS)
    hv = E["res"]["hold (the bar)"]["end"]
    for name, _ in VARIANTS:
        table[name].append(E["res"][name]["end"] / hv - 1)
print(f"\nevery two-year window (Afran, {len(starts)} windows): median, windows beating holding, worst")
for name, _ in VARIANTS:
    v = np.array(table[name]) * 100
    print(f"   {name:32} {np.median(v):+6.1f}%   {np.mean(v > 0.05) * 100:4.0f}%   {v.min():+6.1f}%")
