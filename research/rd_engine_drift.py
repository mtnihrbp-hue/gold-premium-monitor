"""Study E-4, the engine's part 3: the drift's slow anchors (SP_D_HANDOFF.md section 74.10; registered in
b285177 before this run).

Does the dollar's distance from its own 750-day log trend (the stand-in for the dollar against liquidity),
18K's, the dollar's acceleration, or the gap to the world price against its mean, say when fixed income beats
18K over the next 60 or 120 trading days? Walk-forward, refitted monthly, purged by the horizon.

    python research/rd_engine_drift.py
"""

import json
import math
import os
from datetime import date

import numpy as np
from sklearn.linear_model import LogisticRegression

HERE = os.path.dirname(os.path.abspath(__file__))
HORIZONS = (60, 120)
TRAIN_FROM = date(2015, 3, 15)
TEST_FROM = date(2018, 1, 1)
PERIODS = (("P1", date(2018, 1, 1), date(2019, 12, 31)),
           ("P2", date(2020, 1, 1), date(2023, 12, 31)),
           ("P3", date(2024, 1, 1), date(2100, 1, 1)))
NAMES = ["usd_vs_trend", "g18_vs_trend", "usd_acceleration", "gap_vs_mean"]
TREND = 750


def trend_residual(series, i):
    """ln(series[i]) against a straight line fitted to ln(series) over the 750 trading days to i, on the days
    the series has (the dollar misses about 100 days of tgju's record; the first run required every day and so
    produced nothing for the dollar: a defect, fixed before the results were read, SP_D_HANDOFF.md 74.11)."""
    if i < TREND - 1 or series[i] is None or series[i] <= 0:
        return None
    pts = [(k, math.log(series[k])) for k in range(i - TREND + 1, i + 1) if series[k] and series[k] > 0]
    if len(pts) < 500:
        return None
    t = np.array([k for k, _ in pts], dtype=float)
    y = np.array([v for _, v in pts])
    slope, intercept = np.polyfit(t, y, 1)
    return float(y[-1] - (intercept + slope * t[-1]))


def features(rows):
    usd = [r["usd"] for r in rows]
    g = [r["g18"] for r in rows]
    gap = [r["gap"] for r in rows]
    X = []
    for i in range(len(rows)):
        f = [trend_residual(usd, i), trend_residual(g, i), None, None]
        if i >= TREND and usd[i] and usd[i - 250] and usd[i - TREND + 1]:
            recent = math.log(usd[i] / usd[i - 250])
            pace = math.log(usd[i] / usd[i - TREND + 1]) * 250 / (TREND - 1)
            f[2] = recent - pace
        past = [x for x in gap[max(0, i - TREND + 1):i + 1] if x is not None]
        if gap[i] is not None and len(past) >= 500:
            f[3] = gap[i] - sum(past) / len(past)
        X.append(f)
    return X


def targets(rows, h):
    y = [None] * len(rows)
    for i in range(len(rows)):
        a, b = i + 1, i + 1 + h
        if b < len(rows) and rows[a]["fi"] and rows[b]["fi"]:
            y[i] = 1 if math.log(rows[b]["fi"] / rows[a]["fi"]) > math.log(rows[b]["g18"] / rows[a]["g18"]) else 0
    return y


def walk(rows, X, y, h, cols):
    dates = [date.fromisoformat(r["date"]) for r in rows]
    n = len(rows)
    preds = {}
    for (yy, mm) in sorted({(d.year, d.month) for d in dates if d >= TEST_FROM}):
        idx = [i for i in range(n) if dates[i].year == yy and dates[i].month == mm and y[i] is not None]
        if not idx:
            continue
        train = [j for j in range(n) if y[j] is not None and dates[j] >= TRAIN_FROM and j + 1 + h < idx[0]]
        if cols is None:
            base = sum(y[j] for j in train) / len(train)
            for i in idx:
                preds[i] = base
            continue
        tr = [j for j in train if all(X[j][k] is not None for k in cols)]
        te = [i for i in idx if all(X[i][k] is not None for k in cols)]
        if len(tr) < 250 or not te:
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


def main():
    with open(os.path.join(HERE, "data", "panel.json"), encoding="utf-8") as f:
        rows = json.load(f)["rows"]
    dates = [date.fromisoformat(r["date"]) for r in rows]
    X = features(rows)
    passes = []
    for h in HORIZONS:
        y = targets(rows, h)
        print(f"\nH = {h} trading days")
        for name, a, b in PERIODS:
            days = [i for i in range(len(rows)) if a <= dates[i] <= b and y[i] is not None]
            if days:
                print(f"  {name}: {len(days)} test days, {len(days) // h} independent windows, "
                      f"fixed income beat 18K on {sum(y[i] for i in days) / len(days):.0%}")
        p0 = walk(rows, X, y, h, None)
        print(f"  {'model':22} {'P1':>8} {'P2':>8} {'P3':>8}   (Brier skill against the base rate)")
        for label, cols in [("all four", [0, 1, 2, 3])] + [(NAMES[k], [k]) for k in range(4)]:
            pm = walk(rows, X, y, h, cols)
            skills, ok = [], 0
            for name, a, b in PERIODS:
                common = [i for i in pm if a <= dates[i] <= b and i in p0]
                if len(common) < h:
                    skills.append(None)
                    continue
                bm = sum((pm[i] - y[i]) ** 2 for i in common) / len(common)
                b0 = sum((p0[i] - y[i]) ** 2 for i in common) / len(common)
                s = 1 - bm / b0
                skills.append(s)
                ok += s >= 0.05
            if ok >= 2:
                passes.append((h, label))
            cells = " ".join(f"{s:+8.1%}" if s is not None else f"{'-':>8}" for s in skills)
            print(f"  {label:22} {cells}   {'PASS' if ok >= 2 else ''}")
    print("\nPassed:", passes or "none")


if __name__ == "__main__":
    main()
