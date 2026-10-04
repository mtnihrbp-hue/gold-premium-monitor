"""The quant analyst, the drivers' regimes: does world gold's own regime warn of a 2026-type
fall? (SP-D, 2026-10-04; follows research/rd_quant.py)

18K's log return = the dollar's + world gold's + the change in its gap to fair value. Each
driver gets its own two-regime model (statsmodels MarkovRegression: switching mean and
variance) on its daily log returns, fitted on the years before the test year only and
filtered forward. 18K's drift = the dollar's regime drift + world gold's regime drift.
Sized growth-optimally: f* = clip(k * mu / sigma^2, 0, 1), sigma^2 = 18K's EWMA variance,
Davis-Norman no-trade band, Daric's 0.30% round trip. Against holding and against model
D of rd_quant.py (18K's own two regimes).
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
r_g = np.concatenate([[0.0], np.diff(np.log(gc))])
r_u = np.concatenate([[0.0], np.diff(np.log(usd))])
r_x = np.concatenate([[0.0], np.diff(np.log(xau))])
VAR = np.zeros(n)
VAR[0] = np.var(r_g[1:60])
for i in range(1, n):
    VAR[i] = 0.94 * VAR[i - 1] + 0.06 * r_g[i] ** 2
TEST_YEARS = [y for y in sorted({d.year for d in gd}) if y >= 2016]


def fit_filter(r, train_mask, upto_mask):
    """Two-regime fit on the training returns, filtered over the returns up to the test
    year's end: (drift per day, regime means, filtered probabilities, fit); None if EM fails."""
    try:
        model = sm.tsa.MarkovRegression(r[train_mask], k_regimes=2, trend="c", switching_variance=True)
        fit = model.fit(disp=False, search_reps=5)
        full = sm.tsa.MarkovRegression(r[upto_mask], k_regimes=2, trend="c", switching_variance=True)
        probs = full.filter(fit.params).filtered_marginal_probabilities
        probs = probs.values if hasattr(probs, "values") else probs
        means = np.array([fit.params[k] for k, name in enumerate(model.param_names) if name.startswith("const")])
        return probs @ means, means, probs, fit
    except Exception as e:
        print("   fit failed:", type(e).__name__)
        return None


def native(dates, closes):
    """Daily log returns on the instrument's own trading days: no weekend zeros, which made
    one of world gold's two 'regimes' the weekend itself."""
    return np.array(dates[1:]), np.diff(np.log(closes))


def walk_native(dates, closes, per_day_scale):
    """Out-of-sample drift per Iranian trading day, from the instrument's own regimes."""
    d, r = native(dates, closes)
    years = np.array([x.year for x in d])
    mu = np.full(n, np.nan)
    for y in TEST_YEARS:
        out = fit_filter(r, (years >= 2014) & (years < y), years <= y)
        if out is None:
            continue
        drift = out[0]
        dd = list(d[years <= y])
        for i in range(n):
            if gd[i].year == y:
                k = bisect_right(dd, gd[i]) - 1
                if k >= 0:
                    mu[i] = drift[k] * per_day_scale
    return mu


def backtest(mu, lo, hi, cost=0.30, kelly=1.0):
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
        target = f_star if k == 0 else (f_star - band if share < f_star - band else f_star + band if share > f_star + band else None)
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


print("fitting the dollar's and world gold's regimes, walk-forward 2016-2026 ...", flush=True)
mu_u = walk_native(ud, uc, 1.0)
mu_x = walk_native(xd, xc, 252 / 300)      # world gold trades ~252 days a year, 18K ~300
mu_g = walk_native(gd, gc, 1.0)
COMBOS = {"18K's own regimes (D)": mu_g, "dollar + world gold regimes": mu_u + mu_x}
for name, mu in COMBOS.items():
    print(f"\n== {name}: drift below zero on {np.mean(mu[np.isfinite(mu)] < 0) * 100:.0f}% of days")
    for span, lo, hi in (("2016-23", date(2016, 1, 1), date(2023, 12, 31)), ("2024-26", date(2024, 1, 1), date(2027, 1, 1)),
                         ("2026 drop", date(2026, 1, 29), date(2026, 6, 16)), ("01-29->10-01", date(2026, 1, 29), date(2026, 10, 1))):
        for kelly in (1.0, 0.5):
            vals, trades = backtest(mu, lo, hi, kelly=kelly)
            i0, i1 = gd.index(vals[0][0]), gd.index(vals[-1][0])
            hold = gc[i1] / gc[i0] * (1 - 0.0015) / (1 + 0.0015)
            share = np.mean([v[2] for v in vals]) * 100
            print(f"   {span:13} kelly {kelly:.1f}: x{vals[-1][1]:.3f} vs hold x{hold:.3f} ({(vals[-1][1] / hold - 1) * 100:+6.1f}%), "
                  f"{share:3.0f}% in gold on average, {trades} trades")

print("\nworld gold's regime through 2026 (fitted on 2014-2025, on its own trading days)")
xdn, xr = native(xd, xc)
yrs = np.array([x.year for x in xdn])
out = fit_filter(xr, (yrs >= 2014) & (yrs < 2026), np.ones(len(xr), bool))
if out:
    drift, means, probs, fit = out
    print("   regimes:", dict(zip(fit.model.param_names, np.round(fit.params, 5))))
    last = {}
    for k, day in enumerate(xdn):
        if day >= date(2025, 11, 1):
            last[day.strftime("%Y-%m")] = (day, probs[k], drift[k], xc[k + 1])
    for m, (day, pr, dr, x) in last.items():
        print(f"   {day}: world gold ${x:,.0f}  P(regime 1) {pr[1]:.2f}  drift {dr * 252 * 100:+6.1f}%/yr")
