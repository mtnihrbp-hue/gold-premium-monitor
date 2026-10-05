"""The closing hour's order book, on every session (SP-D, 2026-10-05).

rd_fund_book.py saw, on 65 sampled days, Ayyar's closing-hour book imbalance (bid depth - ask depth
over both, top five levels) correlating +0.34 with 18K's next five days. On every session now
(fetch_tsetmc_book.py), after 18K's own last 1, 5 and 20 days and the fund's own day, with a
circular-shift bootstrap for luck; and when it leans hard (beyond +/-0.3), what follows.
"""
import json
import os
import sys
from datetime import date

import numpy as np
from scipy.stats import rankdata

from rd_rebuy import X60, c, d, n

HERE = os.path.dirname(os.path.abspath(__file__))
INS = sys.argv[1] if len(sys.argv) > 1 else "34144395039913458"
B = json.load(open(os.path.join(HERE, "data", "tsetmc_intraday", f"{INS}_book_daily.json"), encoding="utf-8"))
gix = {x: i for i, x in enumerate(d)}
S = {k: np.full(n, np.nan) for k in ("close_hour", "session", "last", "spread")}
for key, rec in B.items():
    i = gix.get(date(int(key[:4]), int(key[4:6]), int(key[6:])))
    if i is None:
        continue
    for k in S:
        if rec.get(k) is not None:
            S[k][i] = rec[k]


def fwd(lag, h):
    out = np.full(n, np.nan)
    out[:n - lag - h] = (c[lag + h:] / c[lag:n - h] - 1) * 100
    return out


def back(k):
    out = np.full(n, np.nan)
    out[k:] = (c[k:] / c[:-k] - 1) * 100
    return out


Y = {"18K today->1d": fwd(0, 1), "18K today->5d": fwd(0, 5), "18K tomorrow->5d": fwd(1, 5), "18K today->20d": fwd(0, 20),
     "gold-FI 60d": X60}
CT = [back(1), back(5), back(20)]
rng = np.random.default_rng(29)
print(f"{sum(1 for r in B.values() if r.get('close_hour') is not None)} sessions with a book")
for label, lo, hi in (("2023-10 -> 2024", date(2023, 10, 1), date(2024, 12, 31)), ("2025 -> 2026-10", date(2025, 1, 1), date(2026, 12, 31)),
                      ("all", date(2023, 1, 1), date(2026, 12, 31))):
    sel = np.array([lo <= x <= hi for x in d])
    for k in ("close_hour", "session", "last"):
        cells = []
        for t, y in Y.items():
            ok = sel & np.isfinite(S[k]) & np.isfinite(y)
            for x in CT:
                ok &= np.isfinite(x)
            m = ok.sum()
            if m < 100:
                cells.append(f"{t} -")
                continue
            X = np.column_stack([np.ones(m)] + [rankdata(x[ok]) / m for x in CT])
            res = lambda v: v - X @ np.linalg.lstsq(X, v, rcond=None)[0]
            a, b = res(rankdata(S[k][ok]) / m), res(rankdata(y[ok]) / m)
            v = np.corrcoef(a, b)[0, 1]
            null = [np.corrcoef(np.roll(a, rng.integers(30, m - 30)), b)[0, 1] for _ in range(300)]
            cells.append(f"{t} {v:+.2f} ({np.mean(np.abs(null) >= abs(v)) * 100:2.0f}%)")
        print(f"   {label:16} {k:10} " + "  ".join(cells))
    ok = sel & np.isfinite(S["close_hour"]) & np.isfinite(Y["18K today->5d"])
    hi_, lo_ = ok & (S["close_hour"] > 0.3), ok & (S["close_hour"] < -0.3)
    print(f"   {label:16} closing hour leaning to bids (>0.3): 18K next 5 days {np.mean(Y['18K today->5d'][hi_]):+.2f}% ({hi_.sum()}), "
          f"to asks (<-0.3): {np.mean(Y['18K today->5d'][lo_]):+.2f}% ({lo_.sum()}), all {np.mean(Y['18K today->5d'][ok]):+.2f}%")
