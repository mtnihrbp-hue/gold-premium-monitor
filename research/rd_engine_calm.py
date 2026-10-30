"""Study E-1, the engine's part 2: calm ahead (SP_D_HANDOFF.md section 74.3; registered in 3b0995a before
this run).

The log of 18K's realised volatility over the 20 trading days from t+2, forecast at t by P (persistence), H
(HAR on 18K's 5, 20 and 60-day volatility) and X (H plus the dollar, Tether, GVZ, VIX, the coin premium's move
and the efficiency ratio). Walk-forward, refitted monthly, purged by 21 days. Forecasts are made from 2015 on
(each out of sample) so E-2 can choose its parameters on earlier years; scored from 2018.
Saves research/data/calm_forecasts.json.

    python research/rd_engine_calm.py
"""

import json
import math
import os
import statistics as st
from datetime import date

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
FORECAST_FROM = date(2015, 1, 1)
SCORE_FROM = date(2018, 1, 1)
PERIODS = (("P1", date(2018, 1, 1), date(2019, 12, 31)),
           ("P2", date(2020, 1, 1), date(2023, 12, 31)),
           ("P3", date(2024, 1, 1), date(2100, 1, 1)))
EPS = 1e-5
RIDGE = 1.0
COMPLETE = float(os.environ.get("CALM_COMPLETE", "0.75"))   # E-1b; 1.0 reproduces E-1
MIN_TETHER_TRAIN = 250
H_NAMES = ["rv5", "rv20", "rv60"]
X_NAMES = H_NAMES + ["usd_rv20", "tether_rv20", "gvz", "gvz_20d", "vix", "coin_move_20d", "efficiency_60d"]


def logret(a, b):
    return math.log(a / b) if a and b and a > 0 and b > 0 else None


def build(rows):
    n = len(rows)
    g = [r["g18"] for r in rows]
    r18 = [None] + [logret(g[i], g[i - 1]) for i in range(1, n)]
    ru = [None] + [logret(rows[i]["usd"], rows[i - 1]["usd"]) for i in range(1, n)]
    rt = [None] + [logret(rows[i]["tether"], rows[i - 1]["tether"]) for i in range(1, n)]

    def rv(series, i, m):
        """The window's realised volatility on the days present. E-1 required every day, so one missing dollar
        or Tether day blanked 20 (75.2); E-1b (G1, SP_D_HANDOFF.md section 76) requires COMPLETE of them."""
        if i - m + 1 < 1:
            return None
        xs = [x for x in series[i - m + 1:i + 1] if x is not None]
        if len(xs) < (m if COMPLETE >= 1 else max(3, math.ceil(COMPLETE * m))):
            return None
        return math.log(st.pstdev(xs) + EPS)

    X = []
    for i in range(n):
        f = {"rv5": rv(r18, i, 5), "rv20": rv(r18, i, 20), "rv60": rv(r18, i, 60), "usd_rv20": rv(ru, i, 20),
             "tether_rv20": rv(rt, i, 20)}
        gv = rows[i].get("gvz_prev")
        gv20 = rows[i - 20].get("gvz_prev") if i >= 20 else None
        f["gvz"] = math.log(gv) if gv else None
        f["gvz_20d"] = math.log(gv / gv20) if gv and gv20 else None
        vx = rows[i].get("vix_prev")
        f["vix"] = math.log(vx) if vx else None
        c0, c1 = rows[i].get("coin_premium"), rows[i - 20].get("coin_premium") if i >= 20 else None
        f["coin_move_20d"] = abs(c0 - c1) if c0 is not None and c1 is not None else None
        if i >= 60 and all(x is not None for x in r18[i - 59:i + 1]):
            denom = sum(abs(x) for x in r18[i - 59:i + 1])
            f["efficiency_60d"] = abs(logret(g[i], g[i - 60])) / denom if denom else None
        else:
            f["efficiency_60d"] = None
        X.append(f)
    y = [None] * n
    for i in range(n):
        fut = r18[i + 2:i + 22]
        if len(fut) == 20 and all(x is not None for x in fut):
            y[i] = math.log(st.pstdev(fut) + EPS)
    return X, y


def fit_predict(train_rows, test_rows, names, ridge):
    A = np.array([[f[k] for k in names] for f, _ in train_rows])
    b = np.array([t for _, t in train_rows])
    mu, sd = A.mean(axis=0), A.std(axis=0)
    sd[sd == 0] = 1
    Z = (A - mu) / sd
    Z1 = np.hstack([np.ones((len(Z), 1)), Z])
    penalty = np.eye(Z1.shape[1]) * ridge
    penalty[0, 0] = 0
    coef = np.linalg.solve(Z1.T @ Z1 + penalty, Z1.T @ b)
    B = np.array([[f[k] for k in names] for f in test_rows])
    return np.hstack([np.ones((len(B), 1)), (B - mu) / sd]) @ coef


def main():
    with open(os.path.join(HERE, "data", "panel.json"), encoding="utf-8") as f:
        rows = json.load(f)["rows"]
    dates = [date.fromisoformat(r["date"]) for r in rows]
    X, y = build(rows)
    n = len(rows)
    preds = {}
    months = sorted({(d.year, d.month) for d in dates if d >= FORECAST_FROM})
    for (yy, mm) in months:
        idx = [i for i in range(n) if dates[i].year == yy and dates[i].month == mm]
        first = idx[0]
        train = [j for j in range(n) if y[j] is not None and j + 21 < first]
        for model, names, ridge in (("H", H_NAMES, 1e-9), ("X", X_NAMES, RIDGE)):
            use = list(names)
            if model == "X" and sum(1 for j in train if X[j]["tether_rv20"] is not None) < MIN_TETHER_TRAIN:
                use.remove("tether_rv20")
            tr = [(X[j], y[j]) for j in train if all(X[j][k] is not None for k in use)]
            te = [i for i in idx if all(X[i][k] is not None for k in use)]
            if len(tr) < 250 or not te:
                continue
            for i, p in zip(te, fit_predict(tr, [X[i] for i in te], use, ridge)):
                preds.setdefault(i, {})[model] = float(p)
            # E-1b: a day missing an input X uses gets X fitted without it, rather than no forecast (G1, 76)
            if model == "X" and COMPLETE < 1:
                for drop in ("tether_rv20", "usd_rv20", "coin_move_20d"):
                    lacking = [i for i in idx if model not in preds.get(i, {}) and X[i][drop] is None and drop in use
                               and all(X[i][k] is not None for k in use if k != drop)]
                    if not lacking:
                        continue
                    sub = [k for k in use if k != drop]
                    tr2 = [(X[j], y[j]) for j in train if all(X[j][k] is not None for k in sub)]
                    if len(tr2) >= 250:
                        for i, p in zip(lacking, fit_predict(tr2, [X[i] for i in lacking], sub, ridge)):
                            preds.setdefault(i, {})[model] = float(p)
        for i in idx:
            if X[i]["rv20"] is not None:
                preds.setdefault(i, {})["P"] = X[i]["rv20"]
    out = {rows[i]["date"]: dict(v, rv20=X[i]["rv20"], rv5=X[i]["rv5"], actual=y[i]) for i, v in sorted(preds.items())}
    name = "calm_forecasts.json" if COMPLETE >= 1 else "calm_forecasts_b.json"
    with open(os.path.join(HERE, "data", name), "w", encoding="utf-8") as f:
        json.dump(out, f)
    print(f"forecasts from {min(out)} to {max(out)}, {len(out)} days")
    print(f"{'period':6} {'days':>5} {'MSE P':>8} {'MSE H':>8} {'MSE X':>8} {'H vs P':>8} {'X vs H':>8} {'rank X':>7}")
    wins_hp = wins_xh = 0
    for name, a, b in PERIODS:
        days = [i for i in preds if a <= dates[i] <= b and y[i] is not None and all(k in preds[i] for k in "PHX")]
        mse = {k: sum((preds[i][k] - y[i]) ** 2 for i in days) / len(days) for k in "PHX"}
        hp, xh = 1 - mse["H"] / mse["P"], 1 - mse["X"] / mse["H"]
        wins_hp += hp >= 0.05
        wins_xh += xh >= 0.05
        xs, ys = [preds[i]["X"] for i in days], [y[i] for i in days]
        rank = np.corrcoef(np.argsort(np.argsort(xs)), np.argsort(np.argsort(ys)))[0, 1]
        print(f"{name:6} {len(days):5} {mse['P']:8.4f} {mse['H']:8.4f} {mse['X']:8.4f} {hp:+8.1%} {xh:+8.1%} {rank:+7.2f}")
    print(f"\nH beats persistence by 5% in {wins_hp} of 3 periods: {'PASS' if wins_hp >= 2 else 'no'}")
    print(f"X beats H by 5% in {wins_xh} of 3 periods: {'PASS' if wins_xh >= 2 else 'no'}")


if __name__ == "__main__":
    main()
