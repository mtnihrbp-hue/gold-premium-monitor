"""Can a learned model tell when waiting pays? Walk-forward on 18K's daily record (SP-D, SP_D_HANDOFF.md
section 40; the owner, 2026-10-16: "R&D models, build scenarios").

rd_when_scenarios.py tested fixed rules: none beat buying at once in both eras. This asks whether a model
finds the days when waiting a month, with the cash in fixed income, would have been cheaper -- the only
reason a decision engine should ever say "wait".

Rules, fixed before the run:
- Data: as rd_when_scenarios.py (tgju's daily 18K, dollar, world gold the day before; the fair gap; the
  fund's level for the carry), from 2015-03-15, where the carry starts.
- Label, for day t: waiting 20 trading days was cheaper, with the waiting rial in fixed income:
  close[t+20] / (close[t] x fi[t+20] / fi[t]) < 1.
- Features, all known at day t's close: the fair gap and its rank over 250 days; 18K against its 20, 50
  and 200-day averages; its 5 and 20-day returns; its 20-day volatility; its distance below the 250-day
  high; the dollar against its 50-day average and its 20-day return; world gold's 20-day return.
- Models: logistic regression (standardised features) and gradient boosting (scikit-learn defaults,
  random_state 0). For each test year Y from 2018, fitted on the days before Y whose label is already
  known (t + 20 trading days before Y's first day).
- The decision: wait 20 days when the model's probability that waiting pays exceeds 0.6; else buy at
  once. Scored on every 20th day of each test year (independent windows) as the cost against buying at
  once, in percent.
- Reported: per year and overall, the base rate of waiting paying, the model's AUC, the share of windows
  it waited, and the strategy's mean cost.
- Verdict, decided now: a model HELPS when the strategy's mean cost is below 0 overall and in at least
  two thirds of the test years, and it waited in at least 10% of the windows; otherwise NO.

Run: python research/rd_when_model.py
"""

import os
import sys
from statistics import mean

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rd_when_scenarios import enrich, load  # noqa: E402

HORIZON = 20
THRESHOLD = 0.6
FIRST_TEST_YEAR = 2018
STEP = 20


def features(rows):
    closes = np.array([r["close"] for r in rows])
    usd = np.array([r["usd"] for r in rows])
    out = []
    for i, r in enumerate(rows):
        if i < 250 or r["rank"] is None or r["fi"] is None:
            out.append(None)
            continue
        c = closes[i]
        rets = np.diff(np.log(closes[i - 20:i + 1]))
        out.append([
            r["gap"], r["rank"],
            c / closes[i - 19:i + 1].mean() - 1, c / closes[i - 49:i + 1].mean() - 1, c / closes[i - 199:i + 1].mean() - 1,
            c / closes[i - 5] - 1, c / closes[i - 20] - 1, float(rets.std()),
            c / closes[i - 249:i + 1].max() - 1,
            usd[i] / usd[i - 49:i + 1].mean() - 1, usd[i] / usd[i - 20] - 1,
            r["world20"],
        ])
    return out


def main():
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    rows = load()
    enrich(rows)
    # world gold's 20-day return, from the gap's parts: fair = 18K / (1 + gap), and fair / dollar is world gold
    fair = [r["close"] / (1 + r["gap"]) / r["usd"] for r in rows]
    for i, r in enumerate(rows):
        r["world20"] = fair[i] / fair[i - 20] - 1 if i >= 20 else 0.0
    X = features(rows)
    n = len(rows)
    label, cost = [None] * n, [None] * n
    for i in range(n - HORIZON):
        a, b = rows[i]["fi"], rows[i + HORIZON]["fi"]
        if X[i] is None or not a or not b:
            continue
        ratio = rows[i + HORIZON]["close"] / (rows[i]["close"] * b / a)
        label[i], cost[i] = int(ratio < 1), (ratio - 1) * 100
    years = sorted({r["day"].year for r in rows if r["day"].year >= FIRST_TEST_YEAR})
    models = {"logistic": lambda: make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000)),
              "boosting": lambda: GradientBoostingClassifier(random_state=0)}
    for name, make in models.items():
        print(f"\n=== {name}")
        print(f"{'year':<6}{'base':>7}{'AUC':>7}{'waited':>8}{'n':>5}{'mean cost':>11}")
        all_costs, year_means, waited_total, windows_total = [], [], 0, 0
        for y in years:
            first = next(i for i, r in enumerate(rows) if r["day"].year == y)
            train = [i for i in range(first - HORIZON) if label[i] is not None]
            test = [i for i, r in enumerate(rows) if r["day"].year == y and label[i] is not None]
            if len(train) < 500 or len(test) < 40:
                continue
            model = make()
            model.fit(np.array([X[i] for i in train]), np.array([label[i] for i in train]))
            p = model.predict_proba(np.array([X[i] for i in test]))[:, 1]
            y_true = [label[i] for i in test]
            auc = roc_auc_score(y_true, p) if len(set(y_true)) > 1 else float("nan")
            prob = dict(zip(test, p))
            windows = test[::STEP]
            costs = [cost[i] if prob[i] > THRESHOLD else 0.0 for i in windows]
            waited = sum(prob[i] > THRESHOLD for i in windows)
            all_costs += costs
            year_means.append(mean(costs))
            waited_total += waited
            windows_total += len(windows)
            print(f"{y:<6}{mean(y_true):>7.0%}{auc:>7.2f}{waited / len(windows):>8.0%}{len(windows):>5}{mean(costs):>+10.2f}%")
        helps = (mean(all_costs) < 0 and sum(m < 0 for m in year_means) >= 2 * len(year_means) / 3
                 and waited_total >= 0.10 * windows_total)
        print(f"overall: mean cost {mean(all_costs):+.2f}% on {windows_total} windows, waited in "
              f"{waited_total / windows_total:.0%}; years below 0: {sum(m < 0 for m in year_means)} of {len(year_means)}")
        print(f"verdict (decided before the run): {'HELPS' if helps else 'NO'}")


if __name__ == "__main__":
    main()
