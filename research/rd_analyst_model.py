"""The comprehensive analyst, R&D: every driver at once, walk-forward (SP-D, 2026-10-04).

The owner: the analyst decides how much gold to hold from the comprehensive analysis,
stays out of downtrends like 2026-01-29 -> 06-16 (-24%), and is far too junior. The
2026 drop was world gold (-19.7%; the dollar -2.2%), a driver the stance never looked at.

FEATURES, causal (day i uses data up to i):
  18K         returns 5/20/60d, distance to SMA20/50/200, RSI14, ADX14, days since a
              52-week high, inside an 8% rally
  dollar      returns 5/20/60d, distance to its SMA50/200
  world gold  returns 5/20/60d, distance to its SMA50/200, drawdown from its 52-week high
  fair gap    18K against world gold x dollar x 0.75/31.1, and its change over 20d
  gold funds  (TSETMC, from 2018) individuals' net buying over 5/20d as a share of the
              value traded, and the value traded against its 60-day average
TARGETS over the next 20 trading days: a drop of 8% or more on the way (the downtrend
detector), a rise of 8% or more, and simply higher.
MODEL: gradient boosting, refitted each year on every earlier year (2016 onward; 2019
onward with the fund features), scored on the next year only. Skill against the base
rate known at the time (Brier), and AUC.
POLICY: the share in gold from the two probabilities, in five steps (0, 25, 50, 75,
100%), one trade a day, Daric's 0.30% round trip; against holding, per Persian quarter,
and over the 2026 drop.
"""
import json
import os
import sys
from bisect import bisect_right
from collections import defaultdict
from datetime import date

import numpy as np
import talib
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
from timeutil import persian_quarter

T = json.load(open(os.path.join(HERE, "data", "tgju_history.json")))
F = json.load(open(os.path.join(HERE, "data", "tsetmc_gold_funds.json"), encoding="utf-8"))
NOT_GOLD = {"سافرون"}
H, BIG = 20, 8.0


def series(k):
    rows = T[k]
    return [date.fromisoformat(r["date"]) for r in rows], np.array([float(r["close"]) for r in rows])


gd, gc = series("geram18")
gh = np.array([float(r["high"]) for r in T["geram18"]])
gl = np.array([float(r["low"]) for r in T["geram18"]])
ud, uc = series("price_dollar_rl")
xd, xc = series("ons")
n = len(gc)


def aligned(dates, closes):
    idx = [bisect_right(dates, d) - 1 for d in gd]
    return np.array([closes[k] if k >= 0 else np.nan for k in idx])


usd, xau = aligned(ud, uc), aligned(xd, xc)
fair = xau * usd * 0.75 / 31.1035


def ret(a, k):
    out = np.full(n, np.nan)
    out[k:] = (a[k:] / a[:-k] - 1) * 100
    return out


def dist(a, period):
    s = talib.SMA(a, period)
    return (a / s - 1) * 100


hi250 = np.array([gc[max(0, i - 249):i + 1].max() for i in range(n)])
since = np.zeros(n)
for i in range(1, n):
    since[i] = 0 if gc[i] >= hi250[i] else since[i - 1] + 1
xhi = np.array([np.nanmax(xau[max(0, i - 249):i + 1]) for i in range(n)])
rally = np.zeros(n)
state, ext = "up", 0
for i in range(n):
    if state == "up":
        if gc[i] > gc[ext]:
            ext = i
        elif gc[i] <= gc[ext] * 0.92:
            state, ext = "down", i
    else:
        if gc[i] < gc[ext]:
            ext = i
        elif gc[i] >= gc[ext] * 1.08:
            state, ext = "up", i
    rally[i] = state == "up"

# gold funds, summed per day
net, traded = defaultdict(float), defaultdict(float)
for code, f in F.items():
    if f["symbol"] in NOT_GOLD:
        continue
    for r in f["flows"]:
        net[str(r["recDate"])] += r["buy_I_Value"] - r["sell_I_Value"]
    for p in f["prices"]:
        traded[p["date"]] += p["value"]
key = [d.strftime("%Y%m%d") for d in gd]
fn = np.array([net.get(k, np.nan) for k in key])
fv = np.array([traded.get(k, np.nan) for k in key])


def rolling_sum(a, k):
    out = np.full(n, np.nan)
    for i in range(k - 1, n):
        w = a[i - k + 1:i + 1]
        if np.isfinite(w).sum() >= k // 2:
            out[i] = np.nansum(w)
    return out


flow5 = rolling_sum(fn, 5) / rolling_sum(fv, 5) * 100
flow20 = rolling_sum(fn, 20) / rolling_sum(fv, 20) * 100
vol60 = np.array([np.nanmean(fv[max(0, i - 59):i + 1]) if i >= 59 else np.nan for i in range(n)])
volz = fv / vol60

gap = (gc / fair - 1) * 100
FEATURES = {
    "g_r5": ret(gc, 5), "g_r20": ret(gc, 20), "g_r60": ret(gc, 60),
    "g_d20": dist(gc, 20), "g_d50": dist(gc, 50), "g_d200": dist(gc, 200),
    "g_rsi": talib.RSI(gc, 14), "g_adx": talib.ADX(gh, gl, gc, 14), "g_since_high": since, "g_rally": rally,
    "u_r5": ret(usd, 5), "u_r20": ret(usd, 20), "u_r60": ret(usd, 60), "u_d50": dist(usd, 50), "u_d200": dist(usd, 200),
    "x_r5": ret(xau, 5), "x_r20": ret(xau, 20), "x_r60": ret(xau, 60), "x_d50": dist(xau, 50), "x_d200": dist(xau, 200),
    "x_dd": (xau / xhi - 1) * 100,
    "gap": gap, "gap_ch20": gap - np.concatenate([np.full(20, np.nan), gap[:-20]]),
}
FUND = {"flow5": flow5, "flow20": flow20, "vol_vs_60d": volz}

fwd = np.full(n, np.nan)
fwd[:n - H] = (gc[H:] / gc[:n - H] - 1) * 100
drop = np.full(n, np.nan)
rise = np.full(n, np.nan)
for i in range(n - H):
    drop[i] = float(gc[i + 1:i + H + 1].min() / gc[i] - 1 <= -BIG / 100)
    rise[i] = float(gc[i + 1:i + H + 1].max() / gc[i] - 1 >= BIG / 100)
TARGETS = {"drop 8%+ within 20d": drop, "rise 8%+ within 20d": rise, "higher after 20d": (fwd > 0).astype(float)}


def matrix(names):
    cols = [FEATURES[k] if k in FEATURES else FUND[k] for k in names]
    return np.column_stack(cols)


def walk_forward(names, first_year, target):
    X = matrix(names)
    years = sorted({d.year for d in gd if d.year >= first_year})
    pred = np.full(n, np.nan)
    for y in years[2:]:
        train = [i for i in range(n - H) if first_year <= gd[i].year < y and np.isfinite(target[i])
                 and (gd[i + H] - gd[i]).days < 60 and gd[i + H].year < y + 1 and gd[i + H] < date(y, 1, 1)]
        test = [i for i in range(n) if gd[i].year == y]
        if len(train) < 500:
            continue
        m = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=200, l2_regularization=1.0,
                                           min_samples_leaf=40, random_state=7)
        m.fit(X[train], target[train])
        pred[test] = m.predict_proba(X[test])[:, 1]
    return pred


def skill(pred, target, sel):
    sel = [i for i in sel if np.isfinite(pred[i]) and np.isfinite(target[i])]
    y, p = target[sel], pred[sel]
    base = np.array([np.mean(target[[j for j in range(i) if np.isfinite(target[j]) and gd[j].year >= 2014][-750:]])
                     for i in sel[::20]])
    base_full = np.repeat(base, 20)[:len(sel)]
    bs, bb = np.mean((p - y) ** 2), np.mean((base_full - y) ** 2)
    return len(sel), roc_auc_score(y, p), (1 - bs / bb) * 100, np.mean(y) * 100


ALL = list(FEATURES)
NO_X = [k for k in ALL if not k.startswith("x_") and k not in ("gap", "gap_ch20")]
PRED = {}
for label, names, first in (("18K + dollar only", NO_X, 2014), ("all price drivers", ALL, 2014),
                            ("all + gold funds", ALL + list(FUND), 2019)):
    print(f"\n== {label}")
    for tname, target in TARGETS.items():
        pred = walk_forward(names, first, target)
        PRED[(label, tname)] = pred
        for span, lo, hi in (("2016-2023", date(2016, 1, 1), date(2023, 12, 31)), ("2024-2026", date(2024, 1, 1), date(2027, 1, 1))):
            sel = [i for i in range(n - H) if lo <= gd[i] <= hi]
            try:
                k, auc, sk, rate = skill(pred, target, sel)
                print(f"   {tname:22} {span}: {k:4} days, AUC {auc:.2f}, Brier skill {sk:+5.1f}% (rate {rate:.0f}%)")
            except Exception as e:
                print(f"   {tname:22} {span}: n/a ({e})")


def policy(label, lo, hi, cost=0.30):
    pd_, pr_ = PRED[(label, "drop 8%+ within 20d")], PRED[(label, "rise 8%+ within 20d")]
    idx = [i for i in range(n - 1) if lo <= gd[i] <= hi and np.isfinite(pd_[i]) and np.isfinite(pr_[i])]
    half = cost / 200
    gold, cash, vals, trades = 0.0, 1.0, [], 0
    for k in range(len(idx) - 1):
        i, j = idx[k], idx[k + 1]
        edge = pr_[i] - pd_[i]
        target = 1.0 if edge > 0.05 else 0.75 if edge > -0.05 else 0.5 if edge > -0.15 else 0.25 if edge > -0.25 else 0.0
        buy, sell = gc[j] * (1 + half), gc[j] * (1 - half)
        value = cash + gold * sell
        share = gold * sell / value
        if abs(target - share) >= 0.2 or (k == 0):
            want, have = target * value, gold * sell
            if want > have:
                spend = min(cash, want - have)
                gold, cash = gold + spend / buy, cash - spend
            else:
                q = (have - want) / sell
                gold, cash = gold - q, cash + q * sell
            trades += 1
        vals.append((gd[j], cash + gold * sell))
    return vals, trades


def quarters(vals):
    out, start_v, cur, last = {}, vals[0][1], None, vals[0][1]
    for day, v in vals:
        q = persian_quarter(day)[2]
        if q != cur:
            if cur is not None:
                out[cur] = last / start_v - 1
                start_v = last
            cur = q
        last = v
    out[cur] = last / start_v - 1
    return out


print("\n== policy: share in gold from P(rise 8%) - P(drop 8%), five steps, Daric's cost")
for label in ("all price drivers", "all + gold funds"):
    for span, lo, hi in (("2016-2023", date(2016, 1, 1), date(2023, 12, 31)), ("2024-2026", date(2024, 1, 1), date(2027, 1, 1)),
                         ("2026 drop", date(2026, 1, 29), date(2026, 6, 16)), ("2026-01-29 -> 10-01", date(2026, 1, 29), date(2026, 10, 1))):
        vals, trades = policy(label, lo, hi)
        if not vals:
            continue
        i0, i1 = gd.index(vals[0][0]), gd.index(vals[-1][0])
        hold = gc[i1] / gc[i0]
        qa, qh = quarters(vals), quarters([(gd[i], gc[i] / gc[i0]) for i in range(i0, i1 + 1)])
        ex = [qa[q] - qh[q] for q in qa if q in qh]
        print(f"   {label:18} {span:20} x{vals[-1][1]:.2f} vs hold x{hold:.2f}   quarters better {sum(e > 0.001 for e in ex)} "
              f"worse {sum(e < -0.001 for e in ex)} ({np.mean(ex) * 100:+.1f} pp), {trades} trades")


# -- the drop detector as a risk switch ------------------------------------------------
# Fully invested; cut to CUT when today's P(drop 8%+) ranks in the top TOP% of every
# earlier out-of-sample prediction (no look-ahead); back to fully invested only after
# CALM consecutive days below the median. Fewer, larger decisions than the five steps.

def switch(label, lo, hi, top, cut, calm, cost=0.30):
    pdrop = PRED[(label, "drop 8%+ within 20d")]
    idx = [i for i in range(n - 1) if lo <= gd[i] <= hi and np.isfinite(pdrop[i])]
    half = cost / 200
    gold, cash, vals, trades, cut_on, quiet = 0.0, 1.0, [], 0, False, 0
    for k in range(len(idx) - 1):
        i, j = idx[k], idx[k + 1]
        history = pdrop[:i][np.isfinite(pdrop[:i])]
        if len(history) < 120:
            target = 1.0
        else:
            hi_thr, mid = np.quantile(history, 1 - top / 100), np.quantile(history, 0.5)
            if pdrop[i] >= hi_thr:
                cut_on, quiet = True, 0
            elif cut_on:
                quiet = quiet + 1 if pdrop[i] < mid else 0
                if quiet >= calm:
                    cut_on = False
            target = cut if cut_on else 1.0
        buy, sell = gc[j] * (1 + half), gc[j] * (1 - half)
        value = cash + gold * sell
        share = gold * sell / value
        if abs(target - share) >= 0.2 or k == 0:
            want, have = target * value, gold * sell
            if want > have:
                spend = min(cash, want - have)
                gold, cash = gold + spend / buy, cash - spend
            else:
                q = (have - want) / sell
                gold, cash = gold - q, cash + q * sell
            trades += 1
        vals.append((gd[j], cash + gold * sell))
    return vals, trades


print("\n== risk switch on the drop detector (all price drivers), Daric's cost")
for top, cut, calm in ((10, 0.5, 5), (10, 0.0, 5), (20, 0.5, 5), (10, 0.5, 10), (5, 0.0, 5)):
    row = []
    for span, lo, hi in (("2016-23", date(2016, 1, 1), date(2023, 12, 31)), ("2024-26", date(2024, 1, 1), date(2027, 1, 1)),
                         ("2026 drop", date(2026, 1, 29), date(2026, 6, 16)), ("01-29->10-01", date(2026, 1, 29), date(2026, 10, 1))):
        vals, trades = switch("all price drivers", lo, hi, top, cut, calm)
        i0, i1 = gd.index(vals[0][0]), gd.index(vals[-1][0])
        row.append(f"{span} x{vals[-1][1]:.2f}/hold x{gc[i1] / gc[i0]:.2f} ({trades}t)")
    print(f"   top {top}% -> {cut:.0%}, back after {calm} calm days: " + " | ".join(row))
