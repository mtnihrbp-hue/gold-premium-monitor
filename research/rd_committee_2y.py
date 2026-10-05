"""The committee room, replayed over the last two years: who is the better decision maker?
(SP-D, 2026-10-05)

The owner: "back testing the committee room for the last two years and see which one could
be a better judge and DM to call on buy sell."

THE CONTRACT (the owner's): 135M toman on 1403/07/14 (2024-10-05), whole grams of 18K at
tgju's close with Daric's 0.30% round trip, bought in full on the first day; the swing is 40%
of the grams (the owner's 2 of 5); a sale's cash goes straight into Afran and earns Afran's
own daily total return; a buy takes it back out (0.10% round trip in and out of the fund).
One decision a day, at the close, acted on the same close (lag 0, the owner's contract).
Ends 1405/07/09 (2026-10-01).

THE MEMBERS, each with a lean every day (+1 gold, -1 fixed income, 0 none), causal:
  brake          the quant engine's f* (section 12) under 0.9 -> -1, else +1
  market state   sideways (section 16) and not at a 60-day high -> -1; a 60-day high -> +1
  fair gap       18K's gap to fair value against its 250 days, z-scored: discount -> +1
  real dollar    the dollar against the cost of money, z-scored: behind -> +1
  dollar 20d     the dollar's last 20 days, z-scored: rising -> +1
  world gold 60d world gold's last 60 days, z-scored: rising -> +1
  money flow     the gold funds' buyer power, 20-day mean, z-scored: strong -> +1
  chartist       research/chartist.py's view: above +0.25 -> +1, below -0.25 -> -1
(a z-score leans beyond +/-0.5; signs are the economic priors of section 17)

THE DECISION MAKERS:
  each member alone   swing out on its -1, back as soon as it is no longer -1
  committee           the weight leaning to fixed income among the members with a view:
                      out at 60% or more, back at 30% or less (section 18's rule, the LLM absent)
                      equal weights | the proposed weights | weights learned each quarter
                      (x (1 + share right - 50%), bounded 0.25-3, from section 18)
  follow the leader   each quarter, the member with the best record so far decides alone
  the rule traders    the brave trader (sections 10-14) and the channel trader (section 16)
"""
import json
import os
import sys
from bisect import bisect_right
from collections import defaultdict
from datetime import date

import numpy as np

from chartist import Chartist
from rd_rebuy import FI, SIG, X20, c, d, flat, h, l, n, rows, side

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
from timeutil import persian_quarter, to_jalali  # noqa: E402

START, END = date(2024, 10, 5), date(2026, 10, 1)
GOLD_HALF, FI_HALF, SWING = 0.30 / 200, 0.10 / 200, 0.40
CASH0 = 1_350_000_000

# Afran's own daily total return (a distribution counted at its usual accrual), on 18K's days
af = next(f for f in FI.values() if f["symbol"] == "افران")
p = sorted(((date(int(x["date"][:4]), int(x["date"][4:6]), int(x["date"][6:])), x["close"]) for x in af["prices"]
            if x["close"] > 0), key=lambda t: t[0])
px = np.array([t[1] for t in p], dtype=float)
r = px[1:] / px[:-1] - 1
adj = []
for k in range(len(r)):
    recent = r[max(0, k - 20):k]
    ok = recent[recent > -0.003]
    adj.append((np.median(ok) if len(ok) else 0.0) if r[k] < -0.003 else r[k])
af_days = [t[0] for t in p[1:]]
af_cum = np.concatenate([[0.0], np.cumsum(np.log1p(adj))])
af_level = np.array([np.exp(af_cum[bisect_right(af_days, x)]) for x in d])   # Afran's level on 18K's calendar
af_ret = np.zeros(n)
af_ret[1:] = af_level[1:] / af_level[:-1] - 1

# the members' z-scores (each against its own last 500 days)
def zscore(s, window=500):
    out = np.full(n, np.nan)
    for i in range(window, n):
        w = s[i - window:i]
        w = w[np.isfinite(w)]
        if len(w) > 100 and np.isfinite(s[i]) and np.std(w) > 0:
            out[i] = (s[i] - np.mean(w)) / np.std(w)
    return out


def lean_from_z(z, sign):
    v = np.nan_to_num(z) * sign
    return np.where(v > 0.5, 1, np.where(v < -0.5, -1, 0))


# money flow: buyer power over the gold funds, 20-day mean
F = json.load(open(os.path.join(HERE, "data", "tsetmc_gold_funds.json"), encoding="utf-8"))
agg = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0])
for fund in F.values():
    for f in fund["flows"]:
        s = str(f["recDate"])
        k = date(int(s[:4]), int(s[4:6]), int(s[6:]))
        a = agg[k]
        a[0] += float(f.get("buy_I_Value") or 0)
        a[1] += float(f.get("buy_I_Count") or 0)
        a[2] += float(f.get("sell_I_Value") or 0)
        a[3] += float(f.get("sell_I_Count") or 0)
fdays = sorted(k for k, a in agg.items() if a[1] and a[3] and a[2])
power = np.array([(agg[k][0] / agg[k][1]) / (agg[k][2] / agg[k][3]) for k in fdays])
power20 = np.array([np.mean(power[max(0, j - 19):j + 1]) for j in range(len(power))])
flow = np.array([power20[bisect_right(fdays, x) - 1] if bisect_right(fdays, x) and (x - fdays[bisect_right(fdays, x) - 1]).days < 7
                 else np.nan for x in d])

lc = np.log(c)
ret = np.concatenate([[0.0], np.diff(lc)])
var = np.zeros(n)
var[0] = np.var(ret[1:60])
for i in range(1, n):
    var[i] = 0.94 * var[i - 1] + 0.06 * ret[i] ** 2
F_STAR = np.clip(np.load(os.path.join(HERE, "data", "quant_D.npy")) / var, 0, 1)
high60 = np.array([i >= 60 and c[i] >= c[i - 59:i + 1].max() for i in range(n)])

chart = Chartist(h, l, c, usable=~flat)
chart_score = np.full(n, np.nan)
for i in range(next(k for k in range(n) if d[k] >= date(2018, 1, 1)), n):
    rr = chart.read(i)
    if rr["structure"]:
        chart_score[i] = rr["score"]

LEAN = {
    "brake": np.where(np.nan_to_num(F_STAR, nan=1) < 0.9, -1, 1),
    "market state": np.where(high60, 1, np.where(side, -1, 0)),
    "fair gap": lean_from_z(zscore(SIG["fair gap (low = discount)"]), -1),
    "real dollar": lean_from_z(zscore(SIG["real dollar (low = behind)"]), -1),
    "dollar 20d": lean_from_z(zscore(SIG["dollar 20 days"]), +1),
    "world gold 60d": lean_from_z(zscore(SIG["world gold 60 days"]), +1),
    "money flow": lean_from_z(zscore(flow), +1),
    "chartist": np.where(np.nan_to_num(chart_score) > 0.25, 1, np.where(np.nan_to_num(chart_score) < -0.25, -1, 0)),
}
MEMBERS = list(LEAN)
PROPOSED = {"brake": 2.0, "fair gap": 1.5, "real dollar": 1.5, "market state": 1.5, "dollar 20d": 1.0,
            "world gold 60d": 0.5, "money flow": 0.5, "chartist": 1.0}


def qlabel(i):
    jy, jm, _ = to_jalali(d[i])
    return f"{jy} Q{(jm - 1) // 3 + 1}"


QL = [qlabel(i) for i in range(n)]


# the contract -------------------------------------------------------------------------------
def evaluate(START, END, extra=()):
    """extra: (name, factory) pairs; factory(idx) returns an out_on(i) function."""
    idx = [i for i in range(n) if START <= d[i] <= END]
    i0 = idx[0]
    def simulate(out_on, name=""):
        """out_on(i, state) -> True if the swing should be out of gold after day i's close."""
        grams = int(CASH0 // (c[i0] * (1 + GOLD_HALF)))
        fund = (CASH0 - grams * c[i0] * (1 + GOLD_HALF)) * (1 - FI_HALF)
        out, swing_g, trades, exits = False, 0, 1, []
        values, out_days = [], 0
        for i in idx:
            if i > i0:
                fund *= 1 + af_ret[i]
            want_out = out_on(i)
            sell, buy = c[i] * (1 - GOLD_HALF), c[i] * (1 + GOLD_HALF)
            if want_out and not out:
                swing_g = int(round(grams * SWING))
                if swing_g:
                    grams -= swing_g
                    fund += swing_g * sell * (1 - FI_HALF)
                    out, trades = True, trades + 1
                    exits.append([i, None])
            elif not want_out and out:
                budget = fund * (1 - FI_HALF)
                g = int(budget // buy)
                grams += g
                fund -= g * buy / (1 - FI_HALF)
                out, trades = False, trades + 1
                exits[-1][1] = i
            out_days += out
            values.append(grams * sell + fund)
        if exits and exits[-1][1] is None:
            exits[-1][1] = idx[-1]
        v = np.array(values)
        dd = (v / np.maximum.accumulate(v) - 1).min() * 100
        good = [((np.log(c[b]) - np.log(c[a])) - (np.log(af_level[b]) - np.log(af_level[a]))) < 0 for a, b in exits if b > a]
        return {"end": v[-1], "trades": trades, "out_days": out_days, "dd": dd, "exits": len(exits),
                "good_exits": sum(good), "values": v}


    def member_dm(m):
        return lambda i: LEAN[m][i] == -1


    def committee(weights_at, leave=0.6, back=0.3):
        state = {"out": False}

        def f(i):
            w = weights_at(i)
            opinion = {m: LEAN[m][i] for m in MEMBERS if LEAN[m][i] != 0 and w[m] > 0}
            if len(opinion) < 2:
                share = 0.0
            else:
                share = sum(w[m] for m, v in opinion.items() if v == -1) / sum(w[m] for m in opinion)
            if not state["out"] and share >= leave:
                state["out"] = True
            elif state["out"] and share <= back:
                state["out"] = False
            return state["out"]
        return f


    # a member's record: share of its non-neutral calls right about gold against fixed income
    # over the next 20 days, scored only once the 20 days have passed
    def record(m, upto, since):
        sel = [i for i in range(since, upto - 20) if LEAN[m][i] != 0 and np.isfinite(X20[i])]
        if len(sel) < 10:
            return None
        return np.mean([np.sign(LEAN[m][i]) == np.sign(X20[i]) for i in sel])


    qstarts = [i for i in idx if i == i0 or QL[i] != QL[i - 1]]


    def learned_weights():
        table, w = {}, dict(PROPOSED)
        for k, qs in enumerate(qstarts):
            if k:
                prev = qstarts[k - 1]
                for m in MEMBERS:
                    sc = record(m, qs, prev)
                    if sc is not None:
                        w[m] = float(np.clip(w[m] * (1 + (sc - 0.5)), 0.25 * PROPOSED[m], 3 * PROPOSED[m]))
            table[qs] = dict(w)

        def at(i):
            start = max(q for q in qstarts if q <= i)
            return table[start]
        return at, table


    def follow_leader():
        lead = {}
        for k, qs in enumerate(qstarts):
            scores = {m: record(m, qs, i0 - 500) for m in MEMBERS}
            scores = {m: v for m, v in scores.items() if v is not None}
            lead[qs] = max(scores, key=scores.get) if scores else "brake"

        def f(i):
            start = max(q for q in qstarts if q <= i)
            return LEAN[lead[start]][i] == -1
        return f, lead


    def brave():
        s = {"entry": None, "sold": None, "since": None}

        def f(i):
            if s["entry"] is None:
                s["entry"] = c[i]
                return False
            if s["sold"] is None:
                if c[i] >= s["entry"] * 1.03:
                    s["sold"], s["since"] = c[i], i
                    return True
                return False
            if c[i] <= s["sold"] * 0.985 or i - s["since"] >= 5:
                s["entry"], s["sold"] = c[i], None
                return False
            return True
        return f


    def channel_trader():
        s = {"out": False}

        def f(i):
            if not side[i]:
                s["out"] = False
                return False
            w = c[i - 59:i + 1]
            pos = (c[i] - w.min()) / (w.max() - w.min()) if w.max() > w.min() else 0.5
            if pos >= 0.75:
                s["out"] = True
            elif pos <= 0.25:
                s["out"] = False
            return s["out"]
        return f


    def weekly(fn, every=5):
        """Decide every `every` trading days from the window's start, as the LLM chair does."""
        held = {"v": False}

        def f(i):
            if (i - i0) % every == 0:
                held["v"] = fn(i)
            return held["v"]
        return f

    eq = {m: 1.0 for m in MEMBERS}
    lw_at, lw_table = learned_weights()
    fl, leaders = follow_leader()
    DMS = [("hold (the bar)", lambda i: False)] + [(f"{m} alone", member_dm(m)) for m in MEMBERS] + [
        ("committee, equal weights", committee(lambda i: eq)),
        ("committee, proposed weights", committee(lambda i: PROPOSED)),
        ("committee, learned weights", committee(lw_at)),
        ("committee, proposed, 50% / 25%", committee(lambda i: PROPOSED, 0.5, 0.25)),
        ("committee, proposed, 70% / 40%", committee(lambda i: PROPOSED, 0.7, 0.4)),
        ("follow the leader", fl),
        ("brave trader", brave()),
        ("channel trader", channel_trader()),
        ("committee, proposed, decided weekly", weekly(committee(lambda i: PROPOSED))),
    ] + [(name, factory(idx)) for name, factory in extra]

    res = {name: simulate(fn, name) for name, fn in DMS}
    return {"idx": idx, "i0": i0, "res": res, "qstarts": qstarts, "lw_table": lw_table, "leaders": leaders,
            "record": record}


if __name__ == "__main__":
    E = evaluate(START, END)
    idx, i0, qstarts, lw_table, leaders, record = E["idx"], E["i0"], E["qstarts"], E["lw_table"], E["leaders"], E["record"]
    print(f"{rows[i0]['jdate']} -> {rows[idx[-1]]['jdate']}: 18K {c[i0] / 1e7:.2f}M -> {c[idx[-1]] / 1e7:.2f}M "
          f"({(c[idx[-1]] / c[i0] - 1) * 100:+.0f}%), Afran {(af_level[idx[-1]] / af_level[i0] - 1) * 100:+.0f}%")
    print("\nhow often each member leans each way over the two years (gold / none / fixed income)")
    for m in MEMBERS:
        v = LEAN[m][idx]
        print(f"   {m:15} {np.mean(v == 1) * 100:4.0f}% / {np.mean(v == 0) * 100:4.0f}% / {np.mean(v == -1) * 100:4.0f}%   "
              f"right about gold vs fixed income (20 days) {record(m, idx[-1], i0) * 100 if record(m, idx[-1], i0) else float('nan'):.0f}% of its calls")

    res = E["res"]
    hold = res["hold (the bar)"]["end"]
    print("\n1. THE TWO YEARS, end value from 135M toman (ranked)")
    print("   decision maker                       end      vs hold   trades  days out  worst fall  exits that beat staying")
    for name, rs in sorted(res.items(), key=lambda kv: -kv[1]["end"]):
        print(f"   {name:34} {rs['end'] / 1e7:7.1f}M  {(rs['end'] / hold - 1) * 100:+6.1f}%  {rs['trades']:6}  {rs['out_days']:8}"
              f"  {rs['dd']:+8.1f}%   {rs['good_exits']}/{rs['exits']}")

    print("\n2. BY PERSIAN QUARTER: each decision maker's quarter against holding's (pp)")
    qs = qstarts + [idx[-1] + 1]
    labels = [QL[q] for q in qstarts]
    print("   " + " " * 32 + "".join(f"{x:>10}" for x in labels))
    hv = res["hold (the bar)"]["values"]
    pos = {i: k for k, i in enumerate(idx)}
    hq = []
    for a, b in zip(qs[:-1], qs[1:]):
        ka, kb = pos[a], pos[min(b, idx[-1] + 1) - 1]
        base = hv[ka - 1] if ka else CASH0
        hq.append(hv[kb] / base - 1)
    print("   " + "hold (quarter return)".ljust(32) + "".join(f"{x * 100:+9.1f}%" for x in hq))
    for name, rs in sorted(res.items(), key=lambda kv: -kv[1]["end"]):
        if name.startswith("hold"):
            continue
        v = rs["values"]
        cells = []
        for (a, b), hr in zip(zip(qs[:-1], qs[1:]), hq):
            ka, kb = pos[a], pos[min(b, idx[-1] + 1) - 1]
            base = v[ka - 1] if ka else CASH0
            cells.append(f"{(v[kb] / base - 1 - hr) * 100:+9.1f} ")
        print(f"   {name[:31]:32}" + "".join(cells))

    print("\n3. THE LEARNED WEIGHTS at each quarter's start, and the leader")
    for qsi in qstarts:
        w = lw_table[qsi]
        print(f"   {QL[qsi]}  leader: {leaders[qsi]:15} " + "  ".join(f"{m.split()[0]} {w[m]:.2f}" for m in MEMBERS))

    print("\n4. EACH MEMBER AS A JUDGE, against the base rate (the last two years; gold vs fixed income over 20 days)")
    sel = [i for i in idx if np.isfinite(X20[i])]
    base_gold = np.mean([X20[i] > 0 for i in sel]) * 100
    print(f"   gold beat fixed income on {base_gold:.0f}% of days: a member that always says gold is right that often")
    for m in MEMBERS:
        g = [X20[i] > 0 for i in sel if LEAN[m][i] == 1]
        f_ = [X20[i] < 0 for i in sel if LEAN[m][i] == -1]
        print(f"   {m:15} when it says gold, gold won {np.mean(g) * 100 if g else np.nan:4.0f}% ({len(g):3} days);  "
              f"when it says fixed income, fixed income won {np.mean(f_) * 100 if f_ else np.nan:4.0f}% ({len(f_):3} days, "
              f"base {100 - base_gold:.0f}%)")

    print("\n5. EVERY TWO-YEAR WINDOW since Afran's history allows (one starting each Persian quarter): against holding")
    starts = [i for i in range(1, n) if date(2020, 6, 1) <= d[i] <= date(2024, 10, 5) and QL[i] != QL[i - 1]]
    table = defaultdict(list)
    for si in starts:
        st = d[si]
        en = date(st.year + 2, st.month, min(st.day, 28))
        E2 = evaluate(st, en)
        hv = E2["res"]["hold (the bar)"]["end"]
        for name, rs in E2["res"].items():
            table[name].append(rs["end"] / hv - 1)
    print(f"   {len(starts)} windows, {QL[starts[0]]} -> {QL[starts[-1]]} starts")
    print("   decision maker                       median   beat holding in   worst window   best window")
    for name, v in sorted(table.items(), key=lambda kv: -np.median(kv[1])):
        v = np.array(v) * 100
        print(f"   {name:34} {np.median(v):+6.1f}%   {np.mean(v > 0.05) * 100:5.0f}% of windows   {v.min():+7.1f}%     {v.max():+7.1f}%")
