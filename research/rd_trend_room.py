"""Trend identification in the room (SP-D, SP_D_HANDOFF.md section 32). Pre-registered in d519da5
before this file was run; the rules below are that section's, unchanged.

Candidates (causal, known at day i's close):
  TSMOM k      18K's log return over k trading days minus fixed income's; > 0 gold (+1), < 0 fixed
               income (-1); k = 63, 126, 252, and the majority of the three
  RSI div      at the confirmation of a swing high (the chartist's ZigZag) that is a higher high
               than the previous one, RSI(14) 2 points or more lower at it: -1 for 20 trading days;
               the mirror at swing lows: +1
  MACD div     the same with the MACD line (12/26/9) as a share of the price, any difference
  stretch size when the room swings out: EMA50 distance z-scored over 500 days; z >= +1 sells 60% of
               the grams, z <= 0 sells 20%, otherwise 40%

Tests:
  1 alone      X20 (gold over fixed income, next 20 trading days, log %) by lean, 2016-2020 and
               2021-2026; divergences against 1,000 shuffles of as many dates in the same era
  2 the room   the production room ("veto + turn", 10-day reviews, section 27's weights without money
               flow) with each candidate at weight 1.0 (stretch: its sizing), paired against the room
               as built: 18 Afran windows from 2020, 27 index windows from 2018, offsets 0-9, Daric's
               0.30% and Goldika's 2.37%
Acceptance: +0.5 points or more at the median over offsets, 60% of windows or more improved, worst
window not lower by more than 1 point -- at both costs and in both window sets.
"""
import sys
from collections import defaultdict
from datetime import date

import numpy as np
import talib

import rd_committee_2y as R
import rd_committee_stocks  # noqa: F401  registers "stocks 20d" (the veto's input)
from rd_committee_veto import BASE
from rd_rebuy import X20, fi_log
from rd_room_reentry_sense import variant

sys.stdout.reconfigure(encoding="utf-8")
c, d, n = R.c, R.d, R.n
lc = np.log(c)
TOL = 0.005
HOLD_DAYS = 20

# -- the candidates --------------------------------------------------------------------------
def tsmom(k):
    out = np.zeros(n, dtype=int)
    for i in range(k, n):
        if np.isfinite(fi_log[i]) and np.isfinite(fi_log[i - k]):
            x = (lc[i] - lc[i - k]) - (fi_log[i] - fi_log[i - k])
            out[i] = 1 if x > 0 else -1 if x < 0 else 0
    return out


def divergence(indicator, min_gap):
    """-1 for HOLD_DAYS after a bearish divergence is confirmed, +1 after a bullish one."""
    lean = np.zeros(n, dtype=int)
    events = {"bear": [], "bull": []}
    sw = R.chart.swings                      # (confirmed_on, pivot_day, price, "H" | "L")
    for kind in ("H", "L"):
        s = [x for x in sw if x[3] == kind]
        for prev, cur in zip(s[:-1], s[1:]):
            conf, p_now, p_prev = cur[0], cur[1], prev[1]
            a, b = indicator[p_prev], indicator[p_now]
            if not (np.isfinite(a) and np.isfinite(b)):
                continue
            if kind == "H" and cur[2] > prev[2] * (1 + TOL) and b < a - min_gap:
                events["bear"].append(conf)
            if kind == "L" and cur[2] < prev[2] * (1 - TOL) and b > a + min_gap:
                events["bull"].append(conf)
    for conf, v in sorted([(e, -1) for e in events["bear"]] + [(e, 1) for e in events["bull"]]):
        lean[conf:conf + HOLD_DAYS] = v
    return lean, events


macd_line = talib.MACD(c, 12, 26, 9)[0] / c
CAND = {f"TSMOM {k}": tsmom(k) for k in (63, 126, 252)}
CAND["TSMOM vote"] = np.sign(CAND["TSMOM 63"] + CAND["TSMOM 126"] + CAND["TSMOM 252"]).astype(int)
CAND["RSI div"], EV_RSI = divergence(R.chart.rsi, 2.0)
CAND["MACD div"], EV_MACD = divergence(macd_line, 0.0)
stretch_z = R.zscore(c / talib.EMA(c, 50) - 1)

ERAS = (("2016-2020", date(2016, 1, 1), date(2020, 12, 31)), ("2021-2026", date(2021, 1, 1), date(2026, 10, 1)))


def era_idx(a, b):
    return np.array([i for i in range(n) if a <= d[i] <= b and np.isfinite(X20[i])])


# -- test 1: alone ----------------------------------------------------------------------------
def alone():
    print("1. ALONE: gold over fixed income in the next 20 trading days (log %), mean and days")
    for name, lean in CAND.items():
        cells = []
        for label, a, b in ERAS:
            ix = era_idx(a, b)
            allm = X20[ix].mean()
            gm = X20[ix[lean[ix] == 1]]
            fm = X20[ix[lean[ix] == -1]]
            cells.append(f"{label}: all {allm:+5.2f} | gold {gm.mean() if len(gm) else np.nan:+5.2f} ({len(gm)}) "
                         f"| fixed income {fm.mean() if len(fm) else np.nan:+5.2f} ({len(fm)})")
        print(f"   {name:11} " + "   ".join(cells))
    rng = np.random.default_rng(32)
    print("\n   divergence events against 1,000 shuffles of as many dates in the same era (5-95% band)")
    for name, ev in (("RSI", EV_RSI), ("MACD", EV_MACD)):
        for kind in ("bear", "bull"):
            for label, a, b in ERAS:
                ix = era_idx(a, b)
                hits = [e for e in ev[kind] if a <= d[e] <= b and np.isfinite(X20[e])]
                if len(hits) < 3:
                    print(f"   {name:4} {kind}  {label}: {len(hits)} events, too few")
                    continue
                m = X20[hits].mean()
                sh = np.array([X20[rng.choice(ix, len(hits), replace=False)].mean() for _ in range(1000)])
                lo, hi = np.percentile(sh, [5, 95])
                verdict = "below the band" if m < lo else "above the band" if m > hi else "inside the band"
                print(f"   {name:4} {kind}  {label}: {len(hits):3} events, mean {m:+6.2f} against shuffles "
                      f"{lo:+6.2f} .. {hi:+6.2f}: {verdict}")


# -- test 2: in the room ------------------------------------------------------------------------
NOF = {m: w for m, w in BASE.items() if m != "money flow"}
S = R.LEAN["stocks 20d"]


def room(weights, size=None):
    """The production room ("veto + turn") with given weights; size(i) the share sold at an exit."""
    def outer(k, offset):
        def factory(idx):
            com = {"out": False}
            st = {"held": False, "exit_stocks": 0}
            start = idx[0]

            def committee(i):
                opinion = {m: R.LEAN[m][i] for m in weights if R.LEAN[m][i] != 0 and weights[m] > 0}
                share = 0.0 if len(opinion) < 2 else \
                    sum(weights[m] for m, v in opinion.items() if v == -1) / sum(weights[m] for m in opinion)
                if not com["out"] and share >= 0.6:
                    com["out"] = True
                elif com["out"] and share <= 0.3:
                    com["out"] = False
                return com["out"]

            def f(i):
                v = committee(i)
                if (i - start) % k == offset:
                    want = v
                    if want and not st["held"] and S[i] == 1:
                        want = False
                    if want and not st["held"]:
                        st["exit_stocks"] = S[i]
                        R.SWING = size(i) if size else 0.40
                    st["held"] = want
                elif st["held"]:
                    if S[i] == 1 and st["exit_stocks"] != 1:
                        st["held"] = False
                    st["exit_stocks"] = S[i] if S[i] != 1 else st["exit_stocks"]
                return st["held"]
            return f
        return factory
    return outer


def stretch_size(i):
    z = stretch_z[i]
    if not np.isfinite(z):
        return 0.40
    return 0.60 if z >= 1 else 0.20 if z <= 0 else 0.40


for name, lean in CAND.items():
    R.LEAN[name] = lean
    R.MEMBERS.append(name)
    R.PROPOSED[name] = 0.0            # the engine's own decision makers leave them out

VARIANTS = {"room as built": room(dict(NOF))}
for name in CAND:
    VARIANTS[f"+ {name}"] = room(dict(NOF, **{name: 1.0}))
VARIANTS["stretch size"] = room(dict(NOF), stretch_size)


def windows(first, last, park):
    R.af_level = R.AFRAN_LEVEL if park == "afran" else np.exp(np.nan_to_num(fi_log - np.nanmin(fi_log)))
    R.af_ret = np.zeros(n)
    R.af_ret[1:] = R.af_level[1:] / R.af_level[:-1] - 1
    starts = [i for i in range(1, n) if first <= d[i] <= last and R.QL[i] != R.QL[i - 1]]
    ex = [(f"{v}|{o}", f(10, o)) for v, f in VARIANTS.items() for o in range(10)]
    table = defaultdict(list)
    for si in starts:
        st = d[si]
        E = R.evaluate(st, date(st.year + 2, st.month, min(st.day, 28)), extra=ex)
        R.SWING = 0.40
        hv = E["res"]["hold (the bar)"]["end"]
        for nm, _ in ex:
            table[nm].append(E["res"][nm]["end"] / hv - 1)
    return len(starts), table


def in_room():
    R.AFRAN_LEVEL = R.af_level.copy()
    verdicts = defaultdict(list)
    for cost in (0.30, 2.37):
        R.GOLD_HALF = cost / 200
        for label, first, last, park in (("Afran windows from 2020", date(2020, 6, 1), date(2024, 10, 5), "afran"),
                                         ("index windows from 2018", date(2018, 1, 1), date(2024, 10, 5), "index")):
            nw, t = windows(first, last, park)
            print(f"\n2. IN THE ROOM, round trip {cost:.2f}%, {label} ({nw}), against holding and against the room as built")
            print("   variant          median vs hold      ahead     worst  | paired vs room: median   improved   worst change")
            base = {o: np.array(t[f"room as built|{o}"]) for o in range(10)}
            for v in VARIANTS:
                arr = {o: np.array(t[f"{v}|{o}"]) for o in range(10)}
                meds = [np.median(arr[o]) * 100 for o in range(10)]
                ahead = [np.mean(arr[o] > 0.0005) * 100 for o in range(10)]
                worst = min(arr[o].min() for o in range(10)) * 100
                if v == "room as built":
                    print(f"   {v:16} {min(meds):+5.1f} to {max(meds):+5.1f}%  {min(ahead):3.0f}-{max(ahead):3.0f}%  {worst:+6.1f}%")
                    continue
                diff = {o: (arr[o] - base[o]) * 100 for o in range(10)}
                dmed = np.median([np.median(diff[o]) for o in range(10)])
                imp = np.mean(np.concatenate([diff[o] > 0.05 for o in range(10)])) * 100
                bworst = min(base[o].min() for o in range(10)) * 100
                dworst = worst - bworst
                ok = dmed >= 0.5 and imp >= 60 and dworst >= -1.0
                verdicts[v].append(ok)
                print(f"   {v:16} {min(meds):+5.1f} to {max(meds):+5.1f}%  {min(ahead):3.0f}-{max(ahead):3.0f}%  {worst:+6.1f}%"
                      f"  | {dmed:+6.2f} pp   {imp:5.0f}%   {dworst:+6.2f} pp  {'passes' if ok else ''}")
    print("\nACCEPTANCE (all four of: two costs x two window sets)")
    for v, oks in verdicts.items():
        print(f"   {v:16} {'ADOPT' if all(oks) else 'reject'}  ({sum(oks)} of {len(oks)})")
    # the last two years, reported, not used
    R.GOLD_HALF = 0.30 / 200
    R.af_level = R.AFRAN_LEVEL
    R.af_ret = np.zeros(n)
    R.af_ret[1:] = R.af_level[1:] / R.af_level[:-1] - 1
    ex = [(v, f(10, 0)) for v, f in VARIANTS.items()]
    E = R.evaluate(R.START, R.END, extra=ex)
    R.SWING = 0.40
    hv = E["res"]["hold (the bar)"]["end"]
    print("\nthe last two years (offset 0, Daric's cost; reported, not used): " +
          ", ".join(f"{v} {(E['res'][v]['end'] / hv - 1) * 100:+.1f}%" for v, _ in ex))


if __name__ == "__main__":
    print("how often each candidate leans gold / none / fixed income, 2016-2026:")
    ix = era_idx(date(2016, 1, 1), date(2026, 10, 1))
    for name, lean in CAND.items():
        v = lean[ix]
        print(f"   {name:11} {np.mean(v == 1) * 100:3.0f}% / {np.mean(v == 0) * 100:3.0f}% / {np.mean(v == -1) * 100:3.0f}%")
    print(f"   divergence events since 2014: RSI bear {len(EV_RSI['bear'])}, bull {len(EV_RSI['bull'])}; "
          f"MACD bear {len(EV_MACD['bear'])}, bull {len(EV_MACD['bull'])}\n")
    alone()
    in_room()
