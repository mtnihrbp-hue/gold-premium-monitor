"""Trading more, and the swing with the quant engine's volatility brake (SP-D, 2026-10-04).

The owner: the brave trader pushes, "let it trade more"; the key is a good trading routine
that makes 50% where holding makes 30%. Two questions:

1. What does more activity cost or earn? The swing rule (section 10) with a larger swing
   share, tighter take-profit and faster buy-back, at Daric's 0.30% round trip.
2. The swing plus the volatility brake (rd_quant.py, model D: the growth-optimal share
   mu/sigma^2 from 18K's own two regimes, which beat holding only in 2018's storm): the
   gold share is capped at the brake's f*, and the swing trades inside that cap.

Walk-forward D refitted every year 2016-2026; continuous shares; signal at day i, trade
at day i+1's close; one trade a day.
"""
import itertools
import json
import os
import sys
import warnings
from datetime import date

import numpy as np

warnings.filterwarnings("ignore")
import statsmodels.api as sm

HERE = os.path.dirname(os.path.abspath(__file__))
rows = json.load(open(os.path.join(HERE, "data", "tgju_history.json")))["geram18"]
d = [date.fromisoformat(r["date"]) for r in rows]
c = np.array([float(r["close"]) for r in rows])
n = len(c)
ret = np.concatenate([[0.0], np.diff(np.log(c))])
VAR = np.zeros(n)
VAR[0] = np.var(ret[1:60])
for i in range(1, n):
    VAR[i] = 0.94 * VAR[i - 1] + 0.06 * ret[i] ** 2

CACHE = os.path.join(HERE, "data", "quant_D.npy")
if os.path.exists(CACHE):
    MU = np.load(CACHE)
else:
    MU = np.full(n, np.nan)
    for y in range(2016, d[-1].year + 1):
        train = np.array([2014 <= x.year < y for x in d])
        upto = np.array([x.year <= y for x in d])
        model = sm.tsa.MarkovRegression(ret[train][1:], k_regimes=2, trend="c", switching_variance=True)
        fit = model.fit(disp=False, search_reps=5)
        probs = sm.tsa.MarkovRegression(ret[upto][1:], k_regimes=2, trend="c", switching_variance=True) \
            .filter(fit.params).filtered_marginal_probabilities
        probs = probs.values if hasattr(probs, "values") else probs
        means = np.array([fit.params[k] for k, nm in enumerate(model.param_names) if nm.startswith("const")])
        drift = np.full(n, np.nan)
        drift[np.flatnonzero(upto)[1:]] = probs @ means
        MU[[i for i in range(n) if d[i].year == y]] = drift[[i for i in range(n) if d[i].year == y]]
    np.save(CACHE, MU)
F_STAR = np.clip(MU / VAR, 0, 1)


def run(lo, hi, swing, take, re_buy, max_out, brake, cost=0.30):
    idx = [i for i in range(n - 1) if lo <= d[i] <= hi and np.isfinite(F_STAR[i])]
    half = cost / 200
    gold, cash, entry, sold_at, out_since, trades, vals = 0.0, 1.0, None, None, None, 0, []
    for k in range(len(idx) - 1):
        i, j = idx[k], idx[k + 1]
        cap = F_STAR[i] if brake else 1.0
        if sold_at is None:
            target = cap * (1 - swing) if (entry and c[i] >= entry * (1 + take / 100)) else cap
        else:
            back = c[i] <= sold_at * (1 - re_buy / 100) or k - out_since >= max_out
            target = cap if back else cap * (1 - swing)
        buy, sell = c[j] * (1 + half), c[j] * (1 - half)
        value = cash + gold * sell
        share = gold * sell / value
        if abs(target - share) > 0.05 or k == 0:
            want, have = target * value, gold * sell
            if want > have:
                spend = min(cash, want - have)
                gold, cash = gold + spend / buy, cash - spend
                if sold_at is not None or entry is None:
                    entry, sold_at, out_since = c[j], None, None
            else:
                q = (have - want) / sell
                gold, cash = gold - q, cash + q * sell
                if target > 0 and sold_at is None and target < cap:
                    sold_at, out_since = c[j], k
            trades += 1
        vals.append(cash + gold * sell)
    i0, i1 = idx[0] + 1, idx[-1]
    return vals[-1], c[i1] / c[i0] * (1 - half) / (1 + half), trades


SPANS = (("2016-23", date(2016, 1, 1), date(2023, 12, 31), 8), ("2024-26", date(2024, 1, 1), date(2027, 1, 1), 2.75))
print("swing share, take-profit, buy back, max days out, brake -> x (vs hold), trades a year")
rows_out = []
for swing, take, re_buy, max_out, brake in itertools.product((0.2, 0.4, 0.6), (3, 4, 5), (1.5, 2), (3, 5), (False, True)):
    res = [run(lo, hi, swing, take, re_buy, max_out, brake) for _, lo, hi, _ in SPANS]
    rows_out.append(((swing, take, re_buy, max_out, brake), res))
base = [run(lo, hi, 0.0, 1e9, 0, 1, False) for _, lo, hi, _ in SPANS]
brake_only = [run(lo, hi, 0.0, 1e9, 0, 1, True) for _, lo, hi, _ in SPANS]
fmt = lambda r, yrs: f"x{r[0]:6.2f} ({(r[0] / r[1] - 1) * 100:+5.1f}% vs hold) {r[2] / yrs:4.0f}/yr"
print("   hold                         " + " | ".join(fmt(r, s[3]) for r, s in zip(base, SPANS)))
print("   brake only                   " + " | ".join(fmt(r, s[3]) for r, s in zip(brake_only, SPANS)))
rows_out.sort(key=lambda x: -(x[1][0][0] / x[1][0][1] + x[1][1][0] / x[1][1][1]))
for params, res in rows_out[:12]:
    swing, take, re_buy, max_out, brake = params
    label = f"swing {swing:.0%} +{take}% -{re_buy}% {max_out}d{' +brake' if brake else ''}"
    print(f"   {label:29}" + " | ".join(fmt(r, s[3]) for r, s in zip(res, SPANS)))
print("   ... the most active rules:")
for params, res in sorted(rows_out, key=lambda x: -x[1][0][2])[:4]:
    swing, take, re_buy, max_out, brake = params
    label = f"swing {swing:.0%} +{take}% -{re_buy}% {max_out}d{' +brake' if brake else ''}"
    print(f"   {label:29}" + " | ".join(fmt(r, s[3]) for r, s in zip(res, SPANS)))
