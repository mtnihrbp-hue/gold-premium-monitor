"""R3 -- probability models for 18K, walk-forward (SP-D research; SP_C_HANDOFF.md 48).

Questions: how much will 18K move in 20/60 trading days (10/50/90% range), will it make
a new 52-week high within 20 days, will it fall 5% on the way. Inputs are the anchors of
section 47 plus the dollar's and world gold's own trends, every one causal: day i uses
data up to i (world gold up to the day before, its close comes after Tehran's).

Each year from 2017 is predicted by models fitted only on earlier years whose outcomes
were known by then, and scored against the plain historical record known at the same
time. A model that does not beat that record adds nothing and is reported as failing.
"""
import json
import os
import warnings
from bisect import bisect_left, bisect_right
from datetime import date

import numpy as np
import talib
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = json.load(open(os.path.join(HERE, "data", "tgju_history.json")))
FIRST_YEAR = 2017
QUANTILES = (0.1, 0.5, 0.9)


def series(inst):
    rows = DATA[inst]
    d = [date.fromisoformat(r["date"]) for r in rows]
    return d, *(np.array([float(r[k]) for r in rows]) for k in ("high", "low", "close"))


def anchors(h, l, c):
    """Causal anchor features of one series, aligned to its own days."""
    out = {}
    for p in (20, 50, 200):
        out[f"dist_sma{p}"] = (c / talib.SMA(c, p) - 1) * 100
    out["spread_50_200"] = (talib.SMA(c, 50) / talib.SMA(c, 200) - 1) * 100
    out["roc20"], out["roc60"] = talib.ROC(c, 20), talib.ROC(c, 60)
    out["rsi14"] = talib.RSI(c, 14)
    out["adx14"] = talib.ADX(h, l, c, 14)
    out["atr_pct"] = talib.ATR(h, l, c, 14) / c * 100
    hi250 = np.array([c[max(0, i - 249):i + 1].max() for i in range(len(c))])
    lo250 = np.array([c[max(0, i - 249):i + 1].min() for i in range(len(c))])
    out["range_pos"] = (c - lo250) / np.where(hi250 > lo250, hi250 - lo250, np.nan) * 100
    since_high = np.full(len(c), np.nan)
    last = None
    for i in range(len(c)):
        if c[i] >= hi250[i]:
            last = i
        since_high[i] = np.nan if last is None else i - last
    out["days_since_high"] = np.minimum(since_high, 250)
    up = talib.SMA(c, 50) > talib.SMA(c, 200)
    age = np.zeros(len(c))
    for i in range(1, len(c)):
        age[i] = age[i - 1] + 1 if up[i] else 0
    out["trend_age"] = np.minimum(age, 1000)
    return out


gd, gh, gl, gc = series("geram18")
n = len(gc)
feats = {f"gold18_{k}": v for k, v in anchors(gh, gl, gc).items()}
for inst, tag, strict in (("price_dollar_rl", "usd", False), ("ons", "xau", True)):
    d, h, l, c = series(inst)
    a = anchors(h, l, c)
    idx = [(bisect_left(d, x) - 1) if strict else (bisect_right(d, x) - 1) for x in gd]
    for k in ("dist_sma50", "dist_sma200", "roc20", "roc60", "days_since_high", "rsi14"):
        feats[f"{tag}_{k}"] = np.array([a[k][j] if j >= 0 else np.nan for j in idx])
names = sorted(feats)
X = np.column_stack([feats[k] for k in names])

hi250 = np.array([gc[max(0, i - 249):i + 1].max() for i in range(n)])
targets = {}
for hzn in (20, 60):
    y = np.full(n, np.nan)
    y[:n - hzn] = (gc[hzn:] / gc[:n - hzn] - 1) * 100
    targets[f"move{hzn}"] = y
nh = np.full(n, np.nan); pb = np.full(n, np.nan); up20 = np.full(n, np.nan)
for i in range(n - 20):
    nh[i] = float(gc[i + 1:i + 21].max() > hi250[i])
    pb[i] = float(gc[i + 1:i + 21].min() / gc[i] - 1 <= -0.05)
    up20[i] = float(gc[i + 20] > gc[i])
years = np.array([x.year for x in gd])
complete = ~np.isnan(X).any(axis=1) & (years >= 2014)


def known_by(year, hzn):
    """Training rows: before `year`, with outcomes known by its first day."""
    first = date(year, 1, 1)
    cut = bisect_left(gd, first) - hzn
    mask = np.zeros(n, bool)
    mask[:max(cut, 0)] = True
    return mask & complete


def brier(p, y):
    return float(np.mean((p - y) ** 2))


def binary_report(label, y, hzn=20):
    print(f"\n== {label}")
    print("  year  days happened | base Brier | logistic Brier  AUC | boosted Brier  AUC")
    agg = {"base": [], "lr": [], "gb": [], "y": []}
    for year in range(FIRST_YEAR, gd[-1].year + 1):
        train = known_by(year, hzn) & ~np.isnan(y)
        test = (years == year) & complete & ~np.isnan(y)
        if test.sum() < 20 or train.sum() < 500:
            continue
        p_base = np.full(test.sum(), y[train].mean())
        lr = make_pipeline(StandardScaler(), LogisticRegression(C=0.3, max_iter=2000)).fit(X[train], y[train])
        gb = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=150,
                                            l2_regularization=1.0, random_state=7).fit(X[train], y[train])
        p_lr, p_gb = lr.predict_proba(X[test])[:, 1], gb.predict_proba(X[test])[:, 1]
        yt = y[test]
        auc = lambda p: roc_auc_score(yt, p) if 0 < yt.mean() < 1 else float("nan")
        print(f"  {year}  {test.sum():4} {yt.mean() * 100:5.0f}%   |   {brier(p_base, yt):.3f}    |    {brier(p_lr, yt):.3f}     {auc(p_lr):.2f} |"
              f"    {brier(p_gb, yt):.3f}     {auc(p_gb):.2f}")
        for k, p in (("base", p_base), ("lr", p_lr), ("gb", p_gb), ("y", yt)):
            agg[k].append(p)
    yy = np.concatenate(agg["y"])
    b = brier(np.concatenate(agg["base"]), yy)
    for k, name in (("lr", "logistic"), ("gb", "boosted")):
        s = brier(np.concatenate(agg[k]), yy)
        print(f"  {name:9} overall Brier {s:.3f} vs base {b:.3f}: skill {(1 - s / b) * 100:+.1f}%  "
              f"AUC {roc_auc_score(yy, np.concatenate(agg[k])):.2f}")
    return agg


def pinball(q, pred, y):
    e = y - pred
    return float(np.mean(np.maximum(q * e, (q - 1) * e)))


def quantile_report(hzn):
    y = targets[f"move{hzn}"]
    print(f"\n== {hzn}-day move, 10/50/90% range: boosted quantile model vs the plain historical quantiles")
    print("  year  days | pinball skill 10% 50% 90% | 10-90% band covered (target 80%): model  plain")
    tot = {q: [[], [], []] for q in QUANTILES}
    cover_m, cover_b = [], []
    for year in range(FIRST_YEAR, gd[-1].year + 1):
        train = known_by(year, hzn) & ~np.isnan(y)
        test = (years == year) & complete & ~np.isnan(y)
        if test.sum() < 20 or train.sum() < 500:
            continue
        preds, base = {}, {}
        for q in QUANTILES:
            m = HistGradientBoostingRegressor(loss="quantile", quantile=q, max_depth=3, learning_rate=0.05,
                                              max_iter=150, l2_regularization=1.0, random_state=7).fit(X[train], y[train])
            preds[q] = m.predict(X[test])
            base[q] = np.full(test.sum(), np.quantile(y[train], q))
            tot[q][0].append(preds[q]); tot[q][1].append(base[q]); tot[q][2].append(y[test])
        skills = [(1 - pinball(q, preds[q], y[test]) / pinball(q, base[q], y[test])) * 100 for q in QUANTILES]
        cm = np.mean((y[test] >= preds[0.1]) & (y[test] <= preds[0.9])) * 100
        cb = np.mean((y[test] >= base[0.1]) & (y[test] <= base[0.9])) * 100
        cover_m.append((cm, test.sum())); cover_b.append((cb, test.sum()))
        print(f"  {year}  {test.sum():4} |   {skills[0]:+5.0f}% {skills[1]:+5.0f}% {skills[2]:+5.0f}%   |   {cm:5.0f}%  {cb:5.0f}%")
    for q in QUANTILES:
        p, b, yy = (np.concatenate(v) for v in tot[q])
        print(f"  overall {q:.0%} quantile: pinball skill {(1 - pinball(q, p, yy) / pinball(q, b, yy)) * 100:+.1f}%")
    w = sum(k for _, k in cover_m)
    print(f"  overall 10-90% coverage: model {sum(c * k for c, k in cover_m) / w:.0f}%, plain {sum(c * k for c, k in cover_b) / w:.0f}%")


print(f"18K tgju {gd[0]}..{gd[-1]}; {len(names)} anchor inputs; walk-forward {FIRST_YEAR}-{gd[-1].year}, refitted yearly")
binary_report("Higher 20 trading days later", up20)
binary_report("New 52-week high within 20 days", nh)
binary_report("Fell 5% or more within 20 days", pb)
quantile_report(20)
quantile_report(60)
