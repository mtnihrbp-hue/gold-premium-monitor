"""SP-Eb.RD, the first forecast study (SP_D_HANDOFF.md section 72.2; registered in 40b7c66 before this run).

Does anything known at a day's close forecast whether 18K beats fixed income over the next 20 or 60 trading
days, better than the base rate? Walk-forward from 2018, refitted monthly, purged by the horizon; 27 models.

    python research/rd_forecast_1.py
"""

import json
import math
import os
from datetime import date

import numpy as np
from sklearn.linear_model import LogisticRegression

HERE = os.path.dirname(os.path.abspath(__file__))
HORIZONS = (20, 60)
TEST_FROM = date(2018, 1, 1)
PERIODS = (("P1", date(2018, 1, 1), date(2019, 12, 31)),
           ("P2", date(2020, 1, 1), date(2023, 12, 31)),
           ("P3", date(2024, 1, 1), date(2100, 1, 1)))
NAMES = ["g18_20d", "g18_vs_50dma", "usd_20d", "tether_5d", "world_20d", "gap", "coin_premium",
         "coin_premium_20d", "tedpix_20d", "fi_rate_60d", "efficiency_60d"]
MIN_TETHER_TRAIN = 250


def load():
    with open(os.path.join(HERE, "data", "panel.json"), encoding="utf-8") as f:
        rows = json.load(f)["rows"]
    return rows


def lr(a, b):
    return math.log(a / b) if a and b and a > 0 and b > 0 else None


def features(rows):
    n = len(rows)
    col = lambda k: [r.get(k) for r in rows]
    g, usd, teth, ons, gap, coin, ted, fi = (col(k) for k in ("g18", "usd", "tether", "ons_prev", "gap", "coin_premium", "tedpix", "fi"))
    X = [[None] * len(NAMES) for _ in range(n)]
    for i in range(n):
        x = X[i]
        if i >= 20:
            x[0] = lr(g[i], g[i - 20])
            x[2] = lr(usd[i], usd[i - 20])
            x[4] = lr(ons[i], ons[i - 20])
            x[8] = lr(ted[i], ted[i - 20])
            x[7] = coin[i] - coin[i - 20] if coin[i] is not None and coin[i - 20] is not None else None
        if i >= 49 and all(v for v in g[i - 49:i + 1]):
            x[1] = (g[i] / (sum(g[i - 49:i + 1]) / 50) - 1) * 100
        if i >= 5:
            x[3] = lr(teth[i], teth[i - 5])
        x[5] = gap[i]
        x[6] = coin[i]
        if i >= 60:
            r = lr(fi[i], fi[i - 60])
            x[9] = r * 250 / 60 if r is not None else None
            steps = [lr(g[j], g[j - 1]) for j in range(i - 59, i + 1)]
            net = lr(g[i], g[i - 60])
            if net is not None and all(s is not None for s in steps) and sum(abs(s) for s in steps) > 0:
                x[10] = abs(net) / sum(abs(s) for s in steps)
    return X


def targets(rows, h):
    n = len(rows)
    y = [None] * n
    for i in range(n):
        a, b = i + 1, i + 1 + h
        if b < n:
            gr, fr = lr(rows[b]["g18"], rows[a]["g18"]), lr(rows[b].get("fi"), rows[a].get("fi"))
            if gr is not None and fr is not None:
                y[i] = 1 if gr > fr else 0
    return y


def run(rows, X, y, h, model):
    """Walk-forward predictions for test days; `model` is "M0", "M1" or a feature index."""
    dates = [date.fromisoformat(r["date"]) for r in rows]
    n = len(rows)
    preds = {}
    months = sorted({(d.year, d.month) for d in dates if d >= TEST_FROM})
    for (yy, mm) in months:
        idx = [i for i in range(n) if dates[i].year == yy and dates[i].month == mm and y[i] is not None]
        if not idx:
            continue
        first = idx[0]
        train = [j for j in range(n) if y[j] is not None and j + 1 + h < first]
        if not train:
            continue
        base = sum(y[j] for j in train) / len(train)
        if model == "M0":
            for i in idx:
                preds[i] = base
            continue
        if model == "M1":
            cols = [k for k in range(len(NAMES)) if k != 3]
            if sum(1 for j in train if X[j][3] is not None) >= MIN_TETHER_TRAIN:
                cols = list(range(len(NAMES)))
        else:
            cols = [model]
        tr = [j for j in train if all(X[j][k] is not None for k in cols)]
        te = [i for i in idx if all(X[i][k] is not None for k in cols)]
        if len(tr) < 100 or not te:
            continue
        A = np.array([[X[j][k] for k in cols] for j in tr])
        mu, sd = A.mean(axis=0), A.std(axis=0)
        sd[sd == 0] = 1
        yt = np.array([y[j] for j in tr])
        if yt.min() == yt.max():
            for i in te:
                preds[i] = float(yt[0])
            continue
        clf = LogisticRegression(C=1.0, max_iter=1000).fit((A - mu) / sd, yt)
        B = np.array([[X[i][k] for k in cols] for i in te])
        for i, p in zip(te, clf.predict_proba((B - mu) / sd)[:, 1]):
            preds[i] = float(p)
    return preds


def brier(pairs):
    return sum((p - o) ** 2 for p, o in pairs) / len(pairs)


def main():
    rows = load()
    X = features(rows)
    dates = [date.fromisoformat(r["date"]) for r in rows]
    models = ["M0", "M1"] + list(range(len(NAMES)))
    passes = []
    for h in HORIZONS:
        y = targets(rows, h)
        print(f"\nH = {h} trading days")
        for name, a, b in PERIODS:
            days = [i for i in range(len(rows)) if a <= dates[i] <= b and y[i] is not None]
            print(f"  {name}: {len(days)} test days, {len(days) // h} independent windows, "
                  f"18K beat fixed income on {sum(y[i] for i in days) / len(days):.0%}")
        p0 = run(rows, X, y, h, "M0")
        print(f"  {'model':22} {'P1':>8} {'P2':>8} {'P3':>8}   (Brier skill against the base rate, on each model's days)")
        for m in models[1:]:
            pm = run(rows, X, y, h, m)
            label = "M1 all features" if m == "M1" else f"M2.{m + 1} {NAMES[m]}"
            skills, ok = [], 0
            for name, a, b in PERIODS:
                common = [i for i in pm if a <= dates[i] <= b and i in p0]
                if len(common) < h:
                    skills.append(None)
                    continue
                s = 1 - brier([(pm[i], y[i]) for i in common]) / brier([(p0[i], y[i]) for i in common])
                skills.append(s)
                ok += s >= 0.05
            if ok >= 2:
                passes.append((h, label))
            cells = " ".join(f"{s:+8.1%}" if s is not None else f"{'-':>8}" for s in skills)
            print(f"  {label:22} {cells}   {'PASS' if ok >= 2 else ''}")
    print("\nPassed (skill of +5% or more in 2 of 3 periods):", passes or "none")


if __name__ == "__main__":
    main()
