"""E-5, the risk of a fall (SP_D_HANDOFF.md section 77.1; registered in 05f1586 before this run).

y = 1 when 18K's lowest close in the 40 trading days after t+1 is 10% or more below t+1's close. M0 the base
rate; R10 a ridge logistic (C = 0.3) on the 10 inputs G4 pointed to; R3 on three. Walk-forward, monthly, purged
by 41 days, trained from 2015-03, tested from 2018. A missing input falls back to the fit without it. Saves the
walk-forward probabilities to research/data/fall_risk.json for E-6.

    python research/rd_fall_risk.py
"""

import json
import os
import sys
from datetime import date

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rd_windows_read as g4  # noqa: E402 -- the drivers, as G4 read them

H, DROP = 40, -0.10
TRAIN_FROM, TEST_FROM = date(2015, 3, 15), date(2018, 1, 1)
PERIODS = (("P1", date(2018, 1, 1), date(2019, 12, 31)),
           ("P2", date(2020, 1, 1), date(2023, 12, 31)),
           ("P3", date(2024, 1, 1), date(2100, 1, 1)))
R10 = ["18K 20d", "18K 60d", "dollar 20d", "dollar acceleration", "real dollar vs 5y", "Tether 5d", "gap to world price",
       "coin premium 20d", "turnover 5d", "calm forecast"]
R3 = ["18K 20d", "real dollar vs 5y", "calm forecast"]


def target(rows):
    g = [r["g18"] for r in rows]
    y = [None] * len(rows)
    for i in range(len(rows) - H - 1):
        base = g[i + 1]
        low = min(g[i + 2:i + 2 + H])
        y[i] = 1 if low / base - 1 <= DROP else 0
    return y


def fit(train, test, F, y, cols, C):
    tr = [j for j in train if all(F[j][k] is not None for k in cols)]
    if len(tr) < 250:
        return {}
    A = np.array([[F[j][k] for k in cols] for j in tr], dtype=float)
    mu, sd = A.mean(axis=0), A.std(axis=0)
    sd[sd == 0] = 1
    yt = np.array([y[j] for j in tr])
    if yt.min() == yt.max():
        return {i: float(yt[0]) for i in test}
    clf = LogisticRegression(C=C, max_iter=2000).fit((A - mu) / sd, yt)
    te = [i for i in test if all(F[i][k] is not None for k in cols)]
    if not te:
        return {}
    B = np.array([[F[i][k] for k in cols] for i in te], dtype=float)
    return dict(zip(te, clf.predict_proba((B - mu) / sd)[:, 1].tolist()))


def walk(rows, F, y, cols):
    dates = [date.fromisoformat(r["date"]) for r in rows]
    n = len(rows)
    preds = {}
    for (yy, mm) in sorted({(d.year, d.month) for d in dates if d >= TEST_FROM}):
        idx = [i for i in range(n) if dates[i].year == yy and dates[i].month == mm]
        train = [j for j in range(n) if y[j] is not None and dates[j] >= TRAIN_FROM and j + 1 + H < idx[0]]
        if cols is None:
            base = sum(y[j] for j in train) / len(train)
            for i in idx:
                preds[i] = base
            continue
        got = fit(train, idx, F, y, cols, 0.3)
        lacking = [i for i in idx if i not in got]
        for drop in cols:                       # G1: a missing input falls back to the fit without it
            if not lacking:
                break
            sub = [k for k in cols if k != drop]
            cand = [i for i in lacking if F[i][drop] is None and all(F[i][k] is not None for k in sub)]
            if cand:
                got.update(fit(train, cand, F, y, sub, 0.3))
                lacking = [i for i in idx if i not in got]
        preds.update(got)
    return preds


def main():
    with open(os.path.join(HERE, "data", "panel.json"), encoding="utf-8") as f:
        rows = json.load(f)["rows"]
    with open(os.path.join(HERE, "data", "macro.json"), encoding="utf-8") as f:
        macro = json.load(f)
    with open(os.path.join(HERE, "data", "calm_forecasts_b.json"), encoding="utf-8") as f:
        calm = json.load(f)
    F = g4.drivers(rows, macro, calm)
    y = target(rows)
    dates = [date.fromisoformat(r["date"]) for r in rows]
    p0 = walk(rows, F, y, None)
    results = {"M0": p0}
    for name, cols in (("R10", R10), ("R3", R3)):
        results[name] = walk(rows, F, y, cols)
    print(f"a fall of 10% or more within {H} days after t+1")
    for name, a, b in PERIODS:
        days = [i for i in range(len(rows)) if a <= dates[i] <= b and y[i] is not None]
        print(f"  {name}: {len(days)} days, base rate {sum(y[i] for i in days) / len(days):.0%}, about {len(days) // H} independent windows")
    passes = []
    for name in ("R10", "R3"):
        pm = results[name]
        cells, ok = [], 0
        for pname, a, b in PERIODS:
            common = [i for i in pm if a <= dates[i] <= b and y[i] is not None and i in p0]
            bm = sum((pm[i] - y[i]) ** 2 for i in common) / len(common)
            b0 = sum((p0[i] - y[i]) ** 2 for i in common) / len(common)
            skill = 1 - bm / b0
            ys = [y[i] for i in common]
            auc = roc_auc_score(ys, [pm[i] for i in common]) if 0 < sum(ys) < len(ys) else float("nan")
            ok += skill >= 0.05
            cells.append(f"{pname} skill {skill:+6.1%} AUC {auc:.2f} ({len(common)} days)")
        if ok >= 2:
            passes.append(name)
        print(f"  {name}: " + "; ".join(cells) + ("  PASS" if ok >= 2 else ""))
    print("Passed:", passes or "none")
    out = {rows[i]["date"]: {k: results[k].get(i) for k in results} for i in range(len(rows)) if any(i in results[k] for k in results)}
    with open(os.path.join(HERE, "data", "fall_risk.json"), "w", encoding="utf-8") as f:
        json.dump(out, f)
    last = max(results["R10"]) if results["R10"] else None
    if last is not None:
        print(f"latest: {rows[last]['date']}: R10 {results['R10'][last]:.0%}, R3 {results['R3'].get(last, float('nan')):.0%}, base {p0.get(last, float('nan')):.0%}")


if __name__ == "__main__":
    main()
