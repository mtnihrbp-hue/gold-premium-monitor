"""E-11: a range for 18K over the next 3 and 7 days, decided each day from every dimension (SP_D_HANDOFF.md sections 97.4,
98.3 and 99). Registered: these rules were committed before the run.

The target: 18K's move from the close of day t to the close h trading rows later (h = 3, and 6 for about 7 days), as
the 10th, 50th and 90th percentiles. Every move is put on the calm model's scale, z = log move / (sigma_t * sqrt(h)), with
sigma_t E-1b's forecast daily volatility known at t.

B0, the base: z's own 10th, 50th and 90th percentiles over the training days: the asymmetric band of 98.3, learned
walk-forward.

M1, the model: linear quantile regression of z on the day's inputs, each known at t, standardised on the training days
(a missing input is 0, its training mean):
- the funds: individuals' buyer power over 5 sessions, and their net money over 5 sessions, each ranked in its trailing
  250 days;
- world gold: the ounce's 5-day move, and GVZ (its log);
- Tether: its 5-day move, and its premium over the dollar;
- the dollar: its 5-day and 20-day moves;
- the coin: its premium's 20-day change;
- the platforms: 18K's gap to the world price;
- the chart: 18K's 20-day move, its distance from its 20-day EMA, its place in its 60-day range, its 14-day RSI.

M2: the same inputs, gradient-boosted quantile trees, 100 shallow trees (depth 2), a learning rate of 0.05.

The walk: each test year from 2018 to 2026 is fitted on every day before it whose outcome closed before it.

The scores, out of sample:
- the pinball loss of the three percentiles, on the move itself;
- the share of days inside the 10-90 band, its coverage;
- its mean width.

The periods: P1 2018-2020, P2 2021-2023, P3 2024-2026.

The verdict: a model is kept when its pinball loss is lower than B0's in 2 of 3 periods, at both horizons, and its
coverage stays within 75-85%; otherwise B0 stands.

    python research/rd_range_e11.py
"""

import json
import math
import os
import warnings

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
QS = (0.10, 0.50, 0.90)
HORIZONS = (3, 6)
PERIODS = (("P1", "2018-01-01", "2020-12-31"), ("P2", "2021-01-01", "2023-12-31"), ("P3", "2024-01-01", "2026-12-31"))
NAMES = ("power5", "net5", "ons5", "gvz", "teth5", "teth_prem", "usd5", "usd20", "coin20", "gap", "g20", "ema20",
         "pos60", "rsi14")


def ranked(series, window=250, min_n=100):
    out = [None] * len(series)
    for i, v in enumerate(series):
        if v is None:
            continue
        past = [x for x in series[max(0, i - window):i] if x is not None]
        if len(past) >= min_n:
            out[i] = sum(1 for x in past if x < v) / len(past)
    return out


def load():
    rows = json.load(open(os.path.join(HERE, "data", "panel.json"), encoding="utf-8"))["rows"]
    calm = json.load(open(os.path.join(HERE, "data", "calm_forecasts_b.json"), encoding="utf-8"))
    rows = [r for r in rows if r.get("g18")]
    n = len(rows)
    col = lambda k: [r.get(k) for r in rows]
    g, usd, ons, teth, gvz, coin, gap = col("g18"), col("usd"), col("ons_prev"), col("tether"), col("gvz_prev"), col("coin_premium"), col("gap")
    power, net = col("power_i"), col("net_i")
    move = lambda s, i, k: math.log(s[i] / s[i - k]) if i >= k and s[i] and s[i - k] else None
    power5 = [st5 if (st5 := (np.mean([p for p in power[max(0, i - 4):i + 1] if p is not None]) if any(p is not None for p in power[max(0, i - 4):i + 1]) else None)) is not None else None for i in range(n)]
    net5 = [sum(x for x in net[max(0, i - 4):i + 1] if x is not None) if any(x is not None for x in net[max(0, i - 4):i + 1]) else None for i in range(n)]
    power5, net5 = ranked(power5), ranked(net5)
    ema, e = [], None
    for v in g:
        e = v if e is None else e + (v - e) * 2 / 21
        ema.append(e)
    rsi = [None] * n
    for i in range(14, n):
        d = [g[j] - g[j - 1] for j in range(i - 13, i + 1)]
        up, dn = sum(x for x in d if x > 0), -sum(x for x in d if x < 0)
        rsi[i] = 100 if dn == 0 else 100 - 100 / (1 + up / dn)
    feats = []
    for i in range(n):
        lo, hi = min(g[max(0, i - 59):i + 1]), max(g[max(0, i - 59):i + 1])
        feats.append([power5[i], net5[i], move(ons, i, 5), math.log(gvz[i]) if gvz[i] else None, move(teth, i, 5),
                      (teth[i] / usd[i] - 1) if teth[i] and usd[i] else None, move(usd, i, 5), move(usd, i, 20),
                      (coin[i] - coin[i - 20]) if i >= 20 and coin[i] is not None and coin[i - 20] is not None else None,
                      gap[i], move(g, i, 20), g[i] / ema[i] - 1, (g[i] - lo) / (hi - lo) if hi > lo else 0.5, rsi[i]])
    sigma = [math.exp(calm[r["date"]]["X"]) if r["date"] in calm and calm[r["date"]].get("X") is not None else None for r in rows]
    return rows, g, feats, sigma


def pinball(y, q, tau):
    d = y - q
    return np.mean(np.maximum(tau * d, (tau - 1) * d))


def main():
    from sklearn.ensemble import GradientBoostingRegressor
    from sklearn.linear_model import QuantileRegressor
    warnings.filterwarnings("ignore")
    rows, g, feats, sigma = load()
    dates = [r["date"] for r in rows]
    F = np.array([[np.nan if v is None else v for v in f] for f in feats], dtype=float)
    results = {}
    for h in HORIZONS:
        idx = [i for i in range(len(rows) - h) if sigma[i] and g[i + h]]
        y = {i: math.log(g[i + h] / g[i]) for i in idx}
        scale = {i: sigma[i] * math.sqrt(h) for i in idx}
        preds = {"B0": {}, "M1": {}, "M2": {}}
        for year in range(2018, 2027):
            test = [i for i in idx if dates[i][:4] == str(year)]
            if not test:
                continue
            start = test[0]
            train = [i for i in idx if i + h < start]
            Xtr, ztr = F[train], np.array([y[i] / scale[i] for i in train])
            mu, sd = np.nanmean(Xtr, axis=0), np.nanstd(Xtr, axis=0)
            sd[sd == 0] = 1
            norm = lambda X: np.nan_to_num((X - mu) / sd, nan=0.0)
            Xt = norm(F[test])
            base = np.quantile(ztr, QS)
            m1 = [QuantileRegressor(quantile=q, alpha=0.001, solver="highs").fit(norm(Xtr), ztr).predict(Xt) for q in QS]
            m2 = [GradientBoostingRegressor(loss="quantile", alpha=q, n_estimators=100, max_depth=2, learning_rate=0.05,
                                            random_state=0).fit(norm(Xtr), ztr).predict(Xt) for q in QS]
            for k, i in enumerate(test):
                preds["B0"][i] = [b * scale[i] for b in base]
                preds["M1"][i] = sorted(m1[j][k] * scale[i] for j in range(3))
                preds["M2"][i] = sorted(m2[j][k] * scale[i] for j in range(3))
        results[h] = (y, preds)
        print(f"\n== {h} trading days ({'about 7 days' if h == 6 else '3 days'})")
        print(f"{'period':6} {'model':5} {'pinball':>9} {'vs B0':>7} {'coverage':>9} {'width':>7}")
        for pname, a, b in PERIODS:
            days = [i for i in idx if a <= dates[i] <= b and i in preds["B0"]]
            yy = np.array([y[i] for i in days])
            loss0 = None
            for m in ("B0", "M1", "M2"):
                P = np.array([preds[m][i] for i in days])
                loss = np.mean([pinball(yy, P[:, j], QS[j]) for j in range(3)])
                loss0 = loss if m == "B0" else loss0
                cov = np.mean((yy >= P[:, 0]) & (yy <= P[:, 2]))
                width = np.mean(np.exp(P[:, 2]) - np.exp(P[:, 0]))
                print(f"{pname:6} {m:5} {loss * 1000:9.3f} {(loss / loss0 - 1) * 100 if m != 'B0' else 0:+6.1f}% {cov:9.0%} {width:7.1%}")
    # the verdict, by the registered rule
    for m in ("M1", "M2"):
        ok_all = True
        for h in HORIZONS:
            y, preds = results[h]
            wins, cov_ok = 0, True
            for pname, a, b in PERIODS:
                days = [i for i in preds["B0"] if a <= dates[i] <= b]
                yy = np.array([y[i] for i in days])
                L = {mm: np.mean([pinball(yy, np.array([preds[mm][i][j] for i in days]), QS[j]) for j in range(3)]) for mm in ("B0", m)}
                wins += L[m] < L["B0"]
                P = np.array([preds[m][i] for i in days])
                cov = np.mean((yy >= P[:, 0]) & (yy <= P[:, 2]))
                cov_ok &= 0.75 <= cov <= 0.85
            ok_all &= wins >= 2 and cov_ok
            print(f"{m}, h={h}: lower loss in {wins} of 3 periods; coverage within 75-85%: {cov_ok}")
        print(f"{m}: {'KEPT' if ok_all else 'not kept; B0 stands'}")


if __name__ == "__main__":
    main()
