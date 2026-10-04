"""The quant analyst: growth-optimal sizing on an estimated drift (SP-D, 2026-10-04).

OBJECTIVE. The owner: "the goal is to maximize the money it has at the beginning of the
period vs the last day". Over many periods that is maximizing expected log wealth -- the
Kelly / Merton problem. With cash earning 0 (toman) and no borrowing or shorting, the
optimal share in gold is

    f* = clip( mu / sigma^2 , 0 , 1 )         mu = expected daily log drift of 18K
                                              sigma^2 = its daily variance

and with a cost c per round trip, a NO-TRADE BAND around f* (Davis-Norman; small-cost
asymptotics for log utility): half-width  delta = ( 3/2 * c * f*^2 (1-f*)^2 )^(1/3),
trading only to the band's edge when the share leaves it.

So the analyst's whole job is the drift. Four estimates, each fitted only on the years
before the year it is tested on (refitted every year), applied causally (filtered, never
smoothed):

  A  Kalman local linear trend on log 18K (statsmodels UnobservedComponents, MLE): the
     filtered slope is the drift
  B  A plus the slope's 10-day change (the second derivative), looking h=10 days ahead:
     drift = slope + accel * h / 2
  C  the drivers: the slope of log dollar + the slope of log world gold (each its own
     Kalman fit) + the pull of 18K's gap to fair value back to its mean (AR(1) / OU)
  D  two regimes (statsmodels MarkovRegression, switching mean and variance) on 18K's
     daily log returns: drift = sum of regime probabilities x regime means

sigma: EWMA of squared daily log returns (lambda 0.94). Fractional Kelly k in {0.5, 1}.
Backtest: signal at day i, trade at day i+1's close, one trade a day, continuous shares;
Daric's 0.30% and Goldika's 2.37% round trip. Against holding, per Persian quarter, the
2026 drop on its own.
"""
import json
import os
import sys
import warnings
from bisect import bisect_right
from datetime import date

import numpy as np

warnings.filterwarnings("ignore")
import statsmodels.api as sm

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
from timeutil import persian_quarter

T = json.load(open(os.path.join(HERE, "data", "tgju_history.json")))


def series(k):
    rows = T[k]
    return [date.fromisoformat(r["date"]) for r in rows], np.array([float(r["close"]) for r in rows])


gd, gc = series("geram18")
ud, uc = series("price_dollar_rl")
xd, xc = series("ons")
n = len(gc)
usd = np.array([uc[bisect_right(ud, d) - 1] for d in gd])
xau = np.array([xc[bisect_right(xd, d) - 1] for d in gd])
lg, lu, lx = np.log(gc), np.log(usd), np.log(xau)
lprem = lg - (lx + lu + np.log(0.75 / 31.1035))
ret = np.concatenate([[0.0], np.diff(lg)])
years = sorted({d.year for d in gd})
TEST_YEARS = [y for y in years if y >= 2016]


def ewma_var(r, lam=0.94):
    v = np.zeros(len(r))
    v[0] = np.var(r[1:60])
    for i in range(1, len(r)):
        v[i] = lam * v[i - 1] + (1 - lam) * r[i] ** 2
    return v


VAR = ewma_var(ret)


def llt_slope(y, train_mask):
    """Filtered slope of a local linear trend fitted (MLE) on the training days only."""
    model = sm.tsa.UnobservedComponents(y[train_mask], level="local linear trend")
    fit = model.fit(disp=False, maxiter=200)
    full = sm.tsa.UnobservedComponents(y, level="local linear trend")
    res = full.filter(fit.params)
    return res.filtered_state[1]


def walk(estimator):
    """Out-of-sample drift for every test year, refitting on the years before it."""
    mu = np.full(n, np.nan)
    for y in TEST_YEARS:
        train = np.array([2014 <= d.year < y for d in gd])
        test = np.array([d.year == y for d in gd])
        upto = np.array([d.year <= y for d in gd])
        mu_y = estimator(train, upto)
        mu[test] = mu_y[test[:len(mu_y)]] if len(mu_y) == n else mu_y[test[upto]]
    return mu


def est_A(train, upto):
    s = np.full(n, np.nan)
    s[upto] = llt_slope(lg[upto], train[upto])
    return s


def est_B(train, upto, h=10):
    s = est_A(train, upto)
    accel = np.full(n, np.nan)
    accel[10:] = (s[10:] - s[:-10]) / 10
    return s + accel * h / 2


def est_C(train, upto):
    su, sx = np.full(n, np.nan), np.full(n, np.nan)
    su[upto] = llt_slope(lu[upto], train[upto])
    sx[upto] = llt_slope(lx[upto], train[upto])
    p = lprem[train]
    a, b = np.polyfit(p[:-1], p[1:], 1)            # p[t+1] = a p[t] + b  (AR(1) / OU)
    theta, kappa = b / (1 - a), 1 - a
    pull = -kappa * (lprem - theta)
    return su + sx + pull


def est_D(train, upto):
    r = ret.copy()
    model = sm.tsa.MarkovRegression(r[train][1:], k_regimes=2, trend="c", switching_variance=True)
    fit = model.fit(disp=False, search_reps=5)
    full = sm.tsa.MarkovRegression(r[upto][1:], k_regimes=2, trend="c", switching_variance=True)
    res = full.filter(fit.params)
    probs = res.filtered_marginal_probabilities
    probs = probs.values if hasattr(probs, "values") else probs
    means = np.array([fit.params[k] for k in range(len(fit.params)) if model.param_names[k].startswith("const")])
    drift = np.full(n, np.nan)
    drift[np.flatnonzero(upto)[1:]] = probs @ means
    return drift


def backtest(mu, lo, hi, cost, kelly):
    idx = [i for i in range(n - 1) if lo <= gd[i] <= hi and np.isfinite(mu[i])]
    half = cost / 200
    gold, cash, vals, trades = 0.0, 1.0, [], 0
    for k in range(len(idx) - 1):
        i, j = idx[k], idx[k + 1]
        f_star = float(np.clip(kelly * mu[i] / VAR[i], 0, 1))
        band = (1.5 * cost / 100 * f_star ** 2 * (1 - f_star) ** 2) ** (1 / 3)
        buy, sell = gc[j] * (1 + half), gc[j] * (1 - half)
        value = cash + gold * sell
        share = gold * sell / value
        target = None
        if k == 0:
            target = f_star
        elif share < f_star - band:
            target = f_star - band
        elif share > f_star + band:
            target = f_star + band
        if target is not None and abs(target - share) > 1e-3:
            want, have = target * value, gold * sell
            if want > have:
                spend = min(cash, want - have)
                gold, cash = gold + spend / buy, cash - spend
            else:
                q = (have - want) / sell
                gold, cash = gold - q, cash + q * sell
            trades += 1
        vals.append((gd[j], cash + gold * sell, gold * sell / (cash + gold * sell)))
    return vals, trades


def quarters(vals):
    out, start_v, cur, last = {}, vals[0][1], None, vals[0][1]
    for day, v, *_ in vals:
        q = persian_quarter(day)[2]
        if q != cur:
            if cur is not None:
                out[cur] = last / start_v - 1
                start_v = last
            cur = q
        last = v
    out[cur] = last / start_v - 1
    return out


SPANS = (("2016-23", date(2016, 1, 1), date(2023, 12, 31)), ("2024-26", date(2024, 1, 1), date(2027, 1, 1)),
         ("2026 drop", date(2026, 1, 29), date(2026, 6, 16)), ("01-29->10-01", date(2026, 1, 29), date(2026, 10, 1)))
print("fitting (walk-forward, refit every year 2016-2026) ...", flush=True)
DRIFTS = {"A slope (Kalman)": walk(est_A), "B slope + acceleration": walk(est_B),
          "C drivers + fair-gap pull": walk(est_C), "D two regimes": walk(est_D)}

for name, mu in DRIFTS.items():
    m = mu[np.isfinite(mu)]
    print(f"\n== {name}: drift per year median {np.median(m) * 250 * 100:+.0f}%, below zero on {np.mean(m < 0) * 100:.0f}% of days")
    for cost, venue in ((0.30, "Daric"), (2.37, "Goldika")):
        for kelly in (0.5, 1.0):
            row = []
            for span, lo, hi in SPANS:
                vals, trades = backtest(mu, lo, hi, cost, kelly)
                i0, i1 = gd.index(vals[0][0]), gd.index(vals[-1][0])
                hold = gc[i1] / gc[i0] * (1 - cost / 200) / (1 + cost / 200)
                q, qh = quarters(vals), quarters([(gd[i], gc[i] / gc[i0]) for i in range(i0, i1 + 1)])
                ex = [q[k] - qh[k] for k in q if k in qh]
                avg_share = np.mean([v[2] for v in vals]) * 100
                row.append(f"{span} x{vals[-1][1]:.2f}/{hold:.2f} q{sum(e > .001 for e in ex)}-{sum(e < -.001 for e in ex)} "
                           f"{avg_share:.0f}%in {trades}t")
            print(f"   {venue:7} kelly {kelly:.1f}: " + " | ".join(row))


# -- where did D's edge come from? ------------------------------------------------------
if os.environ.get("QUANT_DIAG"):
    mu = DRIFTS["D two regimes"]
    print("\nD two regimes, full Kelly, Daric: year by year against holding")
    for y in TEST_YEARS:
        vals, trades = backtest(mu, date(y, 1, 1), date(y, 12, 31), 0.30, 1.0)
        if not vals:
            continue
        i0, i1 = gd.index(vals[0][0]), gd.index(vals[-1][0])
        hold = gc[i1] / gc[i0]
        low = min(v[2] for v in vals) * 100
        out_days = sum(v[2] < 0.9 for v in vals)
        print(f"   {y}: x{vals[-1][1]:.3f} vs hold x{hold:.3f} ({(vals[-1][1] / hold - 1) * 100:+5.1f}%), {trades:3} trades, "
              f"lowest share {low:3.0f}%, days under 90% in gold {out_days}")
    train = np.array([2014 <= d.year < 2026 for d in gd])
    fit = sm.tsa.MarkovRegression(ret[train][1:], k_regimes=2, trend="c", switching_variance=True).fit(disp=False, search_reps=5)
    print("   regimes fitted on 2014-2025:", dict(zip(fit.model.param_names, np.round(fit.params, 5))))
