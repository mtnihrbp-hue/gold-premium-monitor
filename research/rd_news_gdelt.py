"""The news leg, R&D: does GDELT's coverage of Iran and gold lead the drivers? (SP-D, 2026-10-04)

Data: research/data/gdelt.json (research/fetch_gdelt.py, run on GitHub's runner): per theme
and day since 2017, the articles matching (volume, and its share of all coverage) and their
average tone. Themes: Iran overall, sanctions, nuclear talks, military, Iran's currency;
the gold price, the Federal Reserve, the dollar.

1. EVENT STUDY. Days a theme's share of coverage jumps (z >= 3 against its own 60 days)
   and days its tone falls sharply (5-day change in the bottom 5%): the next 5 and 20
   trading days of the dollar (tgju), world gold and 18K, against all days.
2. THE DROP MODEL WITH NEWS. The walk-forward drop detector of rd_analyst_model.py (18K,
   dollar and world gold features) with and without the news features (each theme's
   share z-score and 5-day tone change): AUC and Brier skill on the years it was not fitted
   on (2019-2026; GDELT starts 2017).
"""
import json
import os
from bisect import bisect_right
from datetime import date, datetime, timedelta

import numpy as np
import talib
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

HERE = os.path.dirname(os.path.abspath(__file__))
T = json.load(open(os.path.join(HERE, "data", "tgju_history.json")))
G = json.load(open(os.path.join(HERE, "data", "gdelt.json")))


def series(k):
    rows = T[k]
    return [date.fromisoformat(r["date"]) for r in rows], np.array([float(r["close"]) for r in rows])


gd, gc = series("geram18")
ud, uc = series("price_dollar_rl")
xd, xc = series("ons")
keep = [i for i, d in enumerate(gd) if d >= date(2017, 3, 1)]
gd = [gd[i] for i in keep]
gc = gc[keep]
n = len(gd)
usd = np.array([uc[bisect_right(ud, d) - 1] for d in gd])
xau = np.array([xc[bisect_right(xd, d) - 1] for d in gd])


def news(theme):
    """(share of coverage z-score vs 60 days, 5-day tone change) on the Tehran trading days,
    from the GDELT days up to and including the day before (no same-day look-ahead)."""
    vol = {datetime.strptime(r[0], "%Y%m%d").date(): (r[1] / r[2] if r[2] else np.nan) for r in G[theme]["volume"]}
    tone = {datetime.strptime(r[0], "%Y%m%d").date(): r[1] for r in G[theme]["tone"]}
    days = sorted(vol)
    share = np.array([vol[d] for d in days])
    tones = np.array([tone.get(d, np.nan) for d in days])
    z = np.full(len(days), np.nan)
    for k in range(60, len(days)):
        w = share[k - 60:k]
        w = w[np.isfinite(w)]
        if len(w) > 30 and np.std(w) > 0:
            z[k] = (share[k] - np.mean(w)) / np.std(w)
    dtone = np.full(len(days), np.nan)
    dtone[5:] = tones[5:] - tones[:-5]
    out_z, out_t = np.full(n, np.nan), np.full(n, np.nan)
    for i, d in enumerate(gd):
        k = bisect_right(days, d - timedelta(days=1)) - 1
        if k >= 0:
            out_z[i], out_t[i] = z[k], dtone[k]
    return out_z, out_t


def fwd(a, h):
    out = np.full(n, np.nan)
    out[:n - h] = (a[h:] / a[:n - h] - 1) * 100
    return out


F = {name: (fwd(a, 5), fwd(a, 20)) for name, a in (("dollar", usd), ("world gold", xau), ("18K", gc))}
themes = [t for t in G if G[t]["volume"]]
NEWS = {t: news(t) for t in themes}

print("1. EVENT STUDY: the next 5 / 20 trading days, mean move (all days in brackets)")
base = {k: (np.nanmean(v[0]), np.nanmean(v[1])) for k, v in F.items()}
print("   all days:      " + "   ".join(f"{k} {b[0]:+.2f} / {b[1]:+.2f}%" for k, b in base.items()))
for t in themes:
    z, dt = NEWS[t]
    lo_tone = np.nanquantile(dt, 0.05)
    for label, mask in ((f"{t}: coverage jump (z>=3)", z >= 3), (f"{t}: tone falls (bottom 5%)", dt <= lo_tone)):
        idx = [i for i in range(n - 20) if mask[i]]
        if len(idx) < 8:
            continue
        cells = []
        for k, (f5, f20) in F.items():
            cells.append(f"{k} {np.nanmean(f5[idx]):+.2f} / {np.nanmean(f20[idx]):+.2f}%")
        print(f"   {label:42} {len(idx):4} days: " + "   ".join(cells))


# 2. the drop model, with and without the news
def ret(a, k):
    out = np.full(n, np.nan)
    out[k:] = (a[k:] / a[:-k] - 1) * 100
    return out


def dist(a, p):
    return (a / talib.SMA(a, p) - 1) * 100


PRICE = [ret(gc, 5), ret(gc, 20), ret(gc, 60), dist(gc, 20), dist(gc, 50), dist(gc, 200),
         ret(usd, 5), ret(usd, 20), ret(usd, 60), dist(usd, 50), ret(xau, 5), ret(xau, 20), ret(xau, 60), dist(xau, 50)]
NEWSF = [x for t in themes for x in NEWS[t]]
H = 20
drop = np.full(n, np.nan)
for i in range(n - H):
    drop[i] = float(gc[i + 1:i + H + 1].min() / gc[i] - 1 <= -0.08)


def walk(cols):
    X = np.column_stack(cols)
    pred = np.full(n, np.nan)
    for y in range(2019, gd[-1].year + 1):
        train = [i for i in range(n - H) if gd[i].year < y and np.isfinite(drop[i]) and gd[i + H] < date(y, 1, 1)]
        test = [i for i in range(n) if gd[i].year == y]
        if len(train) < 400:
            continue
        m = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=200, l2_regularization=1.0,
                                           min_samples_leaf=40, random_state=7)
        m.fit(X[train], drop[train])
        pred[test] = m.predict_proba(X[test])[:, 1]
    return pred


print("\n2. THE DROP DETECTOR (8%+ within 20 days), walk-forward 2019-2026")
for label, cols in (("prices only", PRICE), ("prices + news", PRICE + NEWSF)):
    p = walk(cols)
    for span, lo, hi in (("2019-2023", date(2019, 1, 1), date(2023, 12, 31)), ("2024-2026", date(2024, 1, 1), date(2027, 1, 1))):
        sel = [i for i in range(n - H) if lo <= gd[i] <= hi and np.isfinite(p[i])]
        y, q = drop[sel], p[sel]
        rate = np.mean(drop[[i for i in range(n - H) if gd[i] < lo]])
        skill = (1 - np.mean((q - y) ** 2) / np.mean((rate - y) ** 2)) * 100
        print(f"   {label:15} {span}: {len(sel)} days, AUC {roc_auc_score(y, q):.2f}, Brier skill {skill:+.1f}% (rate {np.mean(y) * 100:.0f}%)")
