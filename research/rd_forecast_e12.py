"""E-12: the forecast bake-off, a range and a chance of a rise for 18K over the next 3 and 6 trading days, from the
methods economists use for this (SP_D_HANDOFF.md section 100). Registered: these rules were committed before the run.

Every model gives, for each day t, the 10th, 50th and 90th percentiles of 18K's log move from t to t+h, and the
chance it is above 0. Fitted walk-forward: each test year, 2018-2026, from the days before it whose outcome closed
before it.

The models:
- B0, the base: the calm model's daily volatility (E-1b) times the training days' own standardised percentiles (98.3, E-11);
- G1, GJR-GARCH(1,1) with skewed-t errors on daily moves (Glosten, Jagannathan and Runkle 1993; Hansen 1994): its
  own volatility and asymmetry, the h-day move simulated 1,000 times from the year's parameters;
- E1, error correction: B0's band moved by the training days' least-squares fit of the standardised move on 18K's
  gap to the world price and that gap's 20-day change (Engle and Granger 1987: when 18K sits far from the world price,
  does the gap close through 18K?);
- Q1, boosted quantiles with conformal calibration: gradient-boosted quantile trees on E-11's 14 inputs and the calm
  volatility, the band widened or narrowed by its errors on the last 250 training days (Romano, Patterson and Candes
  2019);
- C1, the combination: the average of the four models' percentiles, equal weights (Bates and Granger 1969;
  Timmermann 2006);
- D1, the chance of a rise from an L2-regularised logistic regression on the same inputs;
- each other model's chance of a rise is its own distribution's share above 0.

The scores, out of sample, by period (P1 2018-2020, P2 2021-2023, P3 2024-2026):
- the pinball loss of the three percentiles, on the move itself;
- the coverage of the 10-90 band, and its mean width;
- the Brier score of the chance of a rise, against the base rate of the training days;
- the Diebold-Mariano statistic of each model's daily pinball loss against B0's, over 2018-2026, with Newey-West
  errors at h - 1 lags.

The verdict:
- **A range model replaces B0** when its pinball loss is lower in 2 of 3 periods at both horizons, its coverage
  stays within 75-85% in every period, and its Diebold-Mariano statistic is -1.65 or lower at both horizons.
- **A chance of a rise is kept** when its Brier skill over the base rate is +2% or more in 2 of 3 periods at both
  horizons.
- Otherwise B0's range and the base rate stand.

    python research/rd_forecast_e12.py
"""

import math
import os
import sys
import warnings

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rd_range_e11 as e11  # noqa: E402 -- the panel, the inputs, the calm volatility, E-11's pinball

QS = (0.10, 0.50, 0.90)
HORIZONS = (3, 6)
PERIODS = e11.PERIODS


def dm_stat(d, h):
    """Diebold-Mariano: the mean loss difference over its Newey-West standard error, h - 1 lags."""
    d = np.asarray(d, dtype=float)
    n, mu = len(d), d.mean()
    x = d - mu
    var = x @ x / n
    for lag in range(1, h):
        w = 1 - lag / h
        var += 2 * w * (x[lag:] @ x[:-lag]) / n
    return mu / math.sqrt(var / n) if var > 0 else 0.0


def main():
    warnings.filterwarnings("ignore")
    from arch import arch_model
    from sklearn.ensemble import HistGradientBoostingRegressor
    from sklearn.linear_model import LogisticRegression
    rows, g, feats, sigma = e11.load()
    dates = [r["date"] for r in rows]
    n = len(rows)
    F = np.array([[np.nan if v is None else v for v in f] + [s if s else np.nan] for f, s in zip(feats, sigma)], dtype=float)
    ret = np.array([100 * math.log(g[i] / g[i - 1]) if i else 0.0 for i in range(n)])   # daily moves, in percent
    gap = np.array([np.nan if f[9] is None else f[9] for f in feats], dtype=float)
    gap20 = np.array([gap[i] - gap[i - 20] if i >= 20 else np.nan for i in range(n)])
    summary = {}
    for h in HORIZONS:
        idx = [i for i in range(n - h) if sigma[i] and g[i + h]]
        y = {i: math.log(g[i + h] / g[i]) for i in idx}
        scale = {i: sigma[i] * math.sqrt(h) for i in idx}
        P = {m: {} for m in ("B0", "G1", "E1", "Q1", "C1")}
        up = {m: {} for m in ("BASE", "B0", "G1", "E1", "Q1", "D1")}
        for year in range(2018, 2027):
            test = [i for i in idx if dates[i][:4] == str(year)]
            if not test:
                continue
            start = test[0]
            train = [i for i in idx if i + h < start]
            z = np.array([y[i] / scale[i] for i in train])
            base_up = float(np.mean([y[i] > 0 for i in train]))
            zq = np.quantile(z, QS)
            # E1: the error-correction shift of the standardised move
            Xe = np.column_stack([np.ones(len(train)), np.nan_to_num(gap[train]), np.nan_to_num(gap20[train])])
            beta = np.linalg.lstsq(Xe, z, rcond=None)[0]
            # Q1: boosted quantiles with conformal calibration on the last 250 training days
            mu, sd = np.nanmean(F[train], axis=0), np.nanstd(F[train], axis=0)
            sd[sd == 0] = 1
            norm = lambda X: np.nan_to_num((X - mu) / sd, nan=0.0)
            fit, cal = train[:-250], train[-250:]
            zf = np.array([y[i] / scale[i] for i in fit])
            models = [HistGradientBoostingRegressor(loss="quantile", quantile=q, max_depth=3, max_iter=200,
                                                    learning_rate=0.05, random_state=0).fit(norm(F[fit]), zf) for q in QS]
            qcal = np.sort(np.column_stack([m.predict(norm(F[cal])) for m in models]), axis=1)
            zc = np.array([y[i] / scale[i] for i in cal])
            conf = np.quantile(np.maximum(qcal[:, 0] - zc, zc - qcal[:, 2]), 0.8)
            qtest = np.sort(np.column_stack([m.predict(norm(F[test])) for m in models]), axis=1)
            # D1: the chance of a rise
            logit = LogisticRegression(C=0.1, max_iter=2000).fit(norm(F[train]), [y[i] > 0 for i in train])
            pd1 = logit.predict_proba(norm(F[test]))[:, 1]
            # G1: GJR-GARCH(1,1), skewed t, on every day before the year; the year forecast with its parameters
            last = start
            am = arch_model(ret[1:test[-1] + 1], mean="Constant", vol="GARCH", p=1, o=1, q=1, dist="skewt")  # to the year's end
            res = am.fit(last_obs=last - 1, disp="off")
            fc = res.forecast(start=test[0] - 1, horizon=h, method="simulation", simulations=1000, reindex=False)
            sims = fc.simulations.values                     # (days, simulations, horizon), in percent
            for k, i in enumerate(test):
                s = scale[i]
                P["B0"][i] = list(zq * s)
                shift = beta @ np.array([1, np.nan_to_num(gap[i]), np.nan_to_num(gap20[i])])
                P["E1"][i] = list((zq - np.mean(z) + shift) * s)      # B0's band, its centre moved to the fit
                lo, md, hi = qtest[k]
                P["Q1"][i] = [(lo - conf) * s, md * s, (hi + conf) * s]
                row = i - 1 - (test[0] - 1)
                cum = sims[row].sum(axis=1) / 100 if 0 <= row < len(sims) else None
                P["G1"][i] = list(np.quantile(cum, QS)) if cum is not None else P["B0"][i]
                P["C1"][i] = list(np.mean([P[m][i] for m in ("B0", "G1", "E1", "Q1")], axis=0))
                up["BASE"][i] = base_up
                up["B0"][i] = float(np.mean(z > 0))
                up["E1"][i] = float(np.mean(z - np.mean(z) + shift > 0))
                up["G1"][i] = float(np.mean(cum > 0)) if cum is not None else base_up
                up["Q1"][i] = float(np.interp(0, [lo * s, md * s, hi * s], [0.1, 0.5, 0.9], left=0.05, right=0.95))
                up["Q1"][i] = 1 - up["Q1"][i]
                up["D1"][i] = float(pd1[k])
        days_all = sorted(P["B0"])
        print(f"\n== {h} trading days")
        print(f"{'period':6} {'model':5} {'pinball':>8} {'vs B0':>7} {'cover':>6} {'width':>6} | {'Brier':>6} {'skill':>7}")
        summary[h] = {}
        for pname, a, b in PERIODS:
            days = [i for i in days_all if a <= dates[i] <= b]
            yy = np.array([y[i] for i in days])
            brier_base = np.mean([(up["BASE"][i] - (y[i] > 0)) ** 2 for i in days])
            loss0 = None
            for mname in ("B0", "G1", "E1", "Q1", "C1", "D1"):
                if mname != "D1":
                    Q = np.array([P[mname][i] for i in days])
                    loss = np.mean([e11.pinball(yy, Q[:, j], QS[j]) for j in range(3)])
                    loss0 = loss if mname == "B0" else loss0
                    cov = np.mean((yy >= Q[:, 0]) & (yy <= Q[:, 2]))
                    width = np.mean(np.exp(Q[:, 2]) - np.exp(Q[:, 0]))
                else:
                    loss = cov = width = None
                brier = np.mean([(up[mname][i] - (y[i] > 0)) ** 2 for i in days])
                skill = 1 - brier / brier_base
                summary[h].setdefault(mname, []).append({"loss": loss, "loss0": loss0, "cov": cov, "skill": skill})
                left = (f"{loss * 1000:8.3f} {(loss / loss0 - 1) * 100:+6.1f}% {cov:6.0%} {width:6.1%}" if loss is not None
                        else f"{'':8} {'':7} {'':6} {'':6}")
                print(f"{pname:6} {mname:5} {left} | {brier:6.4f} {skill * 100:+6.1f}%")
        for mname in ("G1", "E1", "Q1", "C1"):
            d = []
            for i in days_all:
                l = np.mean([e11.pinball(np.array([y[i]]), np.array([P[mname][i][j]]), QS[j]) for j in range(3)])
                l0 = np.mean([e11.pinball(np.array([y[i]]), np.array([P["B0"][i][j]]), QS[j]) for j in range(3)])
                d.append(l - l0)
            summary[h][mname + "_dm"] = dm_stat(d, h)
            print(f"  Diebold-Mariano {mname} against B0, 2018-2026: {summary[h][mname + '_dm']:+.2f}")
    print("\nTHE VERDICT")
    for mname in ("G1", "E1", "Q1", "C1"):
        ok = all(sum(p["loss"] < p["loss0"] for p in summary[h][mname]) >= 2 and all(0.75 <= p["cov"] <= 0.85 for p in summary[h][mname])
                 and summary[h][mname + "_dm"] <= -1.65 for h in HORIZONS)
        print(f"  range {mname}: {'REPLACES B0' if ok else 'not kept'}")
    for mname in ("B0", "G1", "E1", "Q1", "D1"):
        ok = all(sum(p["skill"] >= 0.02 for p in summary[h][mname]) >= 2 for h in HORIZONS)
        print(f"  chance of a rise {mname}: {'KEPT' if ok else 'not kept'}")


if __name__ == "__main__":
    main()
