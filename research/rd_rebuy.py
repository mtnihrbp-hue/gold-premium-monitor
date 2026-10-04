"""When to take the money out of fixed income and buy gold (SP-D, 2026-10-04).

The owner: "understanding the move is a key; we have to find a proper answer to this, to
take the money out of fixed income and buy gold. This is one of the key questions."

With cash in fixed income the growth-optimal share in gold is f* = (mu - r) / sigma^2, r the
fixed-income return (section 12 had r = 0, so f* was 100% nearly always). In a sideways
market 18K has earned about r (section 16), so the decision is a question about mu - r: what,
known on day i, says gold will beat fixed income over the next 20 / 60 trading days?

Target: 18K's return minus the fixed-income index's (research/data/tsetmc_fixed_income.json)
over the next 20 and 60 days, from the close of day i. Candidates, all causal:

  real dollar    log(dollar / fixed-income level) against its own last 500 days: the dollar
                 behind (below) the cost of money, the pressure a devaluation releases
  real gold      the same for 18K: gold behind the cost of money
  fair gap       18K's gap to fair value (world gold x dollar / 31.1035 x 0.75) against its
                 own last 250 days' median
  world gold 60  world gold's last 60 days
  dollar 20      the dollar's last 20 days
  quiet          20-day volatility over 250-day volatility (a squeeze is low)
  sideways age   days since the current sideways episode began (section 16's definition)

Each against the target on all days and on sideways days, 2016-2020 and 2021-2026: rank
correlation (IC), and a circular-shift bootstrap (keeps the autocorrelation) for luck.
"""
import json
import os
from bisect import bisect_right
from datetime import date

import numpy as np
from scipy.stats import rankdata

HERE = os.path.dirname(os.path.abspath(__file__))
T = json.load(open(os.path.join(HERE, "data", "tgju_history.json")))
FI = json.load(open(os.path.join(HERE, "data", "tsetmc_fixed_income.json"), encoding="utf-8"))
rows = T["geram18"]
d = [date.fromisoformat(r["date"]) for r in rows]
o, h, l, c = (np.array([float(r[k]) for r in rows]) for k in ("open", "high", "low", "close"))
flat = (o == h) & (h == l) & (l == c)
n = len(c)


def aligned(key):
    ds = [date.fromisoformat(r["date"]) for r in T[key]]
    vs = np.array([float(r["close"]) for r in T[key]])
    return np.array([vs[bisect_right(ds, x) - 1] if bisect_right(ds, x) else np.nan for x in d])


usd, ons = aligned("price_dollar_rl"), aligned("ons")

# the fixed-income index (rd_sideways.py section 1): the median fund's daily total return
EQUITY = ("اطلس", "آساس")
fund_ret = []
for f in FI.values():
    if f["symbol"] in EQUITY:
        continue
    p = sorted(((date(int(x["date"][:4]), int(x["date"][4:6]), int(x["date"][6:])), x["close"]) for x in f["prices"]
                if x["close"] > 0), key=lambda t: t[0])
    px = np.array([t[1] for t in p], dtype=float)
    r = px[1:] / px[:-1] - 1
    out = {}
    for k in range(len(r)):
        recent = r[max(0, k - 20):k]
        ok = recent[recent > -0.003]
        out[p[k + 1][0]] = (np.median(ok) if len(ok) else 0.0) if r[k] < -0.003 else r[k]
    fund_ret.append(out)
fi_days = sorted({k for s in fund_ret for k in s})
fi_cum = np.cumsum([np.log1p(np.median([s[k] for s in fund_ret if k in s])) for k in fi_days])
fi_log = np.array([fi_cum[bisect_right(fi_days, x) - 1] if bisect_right(fi_days, x) else np.nan for x in d])

FIRST = next(i for i in range(n) if d[i] >= date(2016, 1, 1))


def forward(logs, hzn):
    out = np.full(n, np.nan)
    out[:n - hzn] = logs[hzn:] - logs[:n - hzn]
    return out


lc = np.log(c)
X20 = (forward(lc, 20) - forward(fi_log, 20)) * 100     # gold over fixed income, log %
X60 = (forward(lc, 60) - forward(fi_log, 60)) * 100


def against_own(x, window, how="mean"):
    out = np.full(n, np.nan)
    for i in range(window, n):
        w = x[i - window:i]
        w = w[np.isfinite(w)]
        if len(w) > window * 0.8:
            out[i] = x[i] - (np.mean(w) if how == "mean" else np.median(w))
    return out


def back(x, k):
    out = np.full(n, np.nan)
    out[k:] = x[k:] - x[:-k]
    return out


ret = np.concatenate([[0.0], np.diff(lc)])
vol20 = np.array([np.std(ret[max(0, i - 19):i + 1]) for i in range(n)])
vol250 = np.array([np.std(ret[max(0, i - 249):i + 1]) for i in range(n)])

N = 60
er = np.full(n, np.nan)
for i in range(N, n):
    if flat[i - N + 1:i + 1].mean() <= 0.3:
        moves = np.abs(np.diff(c[i - N:i + 1])).sum()
        er[i] = abs(c[i] - c[i - N]) / moves if moves else 0
side = np.nan_to_num(er, nan=1) < 1 / np.sqrt(N)
age = np.zeros(n)
for i in range(1, n):
    age[i] = age[i - 1] + 1 if side[i] else 0

SIG = {
    "real dollar (low = behind)": against_own(np.log(usd) - fi_log, 500),
    "real gold (low = behind)": against_own(lc - fi_log, 500),
    "fair gap (low = discount)": against_own(np.log(c / (ons * usd / 31.1035 * 0.75)), 250, "median"),
    "world gold 60 days": back(np.log(ons), 60),
    "dollar 20 days": back(np.log(usd), 20),
    "quiet (low = squeeze)": np.where(vol250 > 0, vol20 / vol250, np.nan),
    "sideways age": np.where(side, age, np.nan),
}
PERIODS = (("2016-2020", date(2016, 1, 1), date(2020, 12, 31)), ("2021-2026", date(2021, 1, 1), date(2026, 12, 31)))
rng = np.random.default_rng(5)


def ic(s, y, sel):
    ok = sel & np.isfinite(s) & np.isfinite(y)
    if ok.sum() < 120:
        return np.nan, np.nan, 0
    a, b = rankdata(s[ok]), rankdata(y[ok])
    v = np.corrcoef(a, b)[0, 1]
    m = ok.sum()
    null = [np.corrcoef(np.roll(a, rng.integers(60, m - 60)), b)[0, 1] for _ in range(300)]
    return v, np.mean(np.abs(null) >= abs(v)), m




def main():
    print("gold over fixed income, all days since 2016: next 20 days "
          f"{np.nanmean(X20[FIRST:]):+.2f}%, next 60 days {np.nanmean(X60[FIRST:]):+.2f}%;"
          f" on sideways days {np.nanmean(X20[FIRST:][side[FIRST:]]):+.2f}% / {np.nanmean(X60[FIRST:][side[FIRST:]]):+.2f}%")
    print("\n1. RANK CORRELATION with gold's return over fixed income (luck = the share of shuffles as strong)")
    for name, s in SIG.items():
        for scope in ("all days", "sideways"):
            cells = []
            for label, lo, hi in PERIODS:
                sel = np.array([lo <= x <= hi for x in d]) & (side if scope == "sideways" else True)
                for hz, y in (("20d", X20), ("60d", X60)):
                    v, p, m = ic(s, y, sel)
                    cells.append(f"{label} {hz} {v:+.2f} ({p * 100:3.0f}%)" if np.isfinite(v) else f"{label} {hz}    -       ")
            print(f"   {name:27} {scope:9} " + "  ".join(cells))

    print("\n2. ON SIDEWAYS DAYS: gold over fixed income in the next 60 days, by fifth of each signal (low -> high)")
    for name, s in SIG.items():
        for label, lo, hi in PERIODS:
            sel = np.array([lo <= x <= hi for x in d]) & side & np.isfinite(s) & np.isfinite(X60)
            if sel.sum() < 100:
                continue
            q = np.nanquantile(s[sel], [0.2, 0.4, 0.6, 0.8])
            bins = np.digitize(s[sel], q)
            cells = [f"{np.mean(X60[sel][bins == k]):+6.1f}" for k in range(5)]
            print(f"   {name:27} {label}: " + " ".join(cells) + f"   ({sel.sum()} days)")

    print("\n3. THE 1405 CHANNEL: the signals on its days (every 10th trading day) and what followed")
    for i in range(n):
        if date(2026, 2, 1) <= d[i] <= date(2026, 9, 1) and i % 10 == 0:
            print(f"   {rows[i]['jdate']} {c[i] / 1e7:5.1f}M {'S' if side[i] else '.'}  "
                  + "  ".join(f"{k.split(' (')[0]} {SIG[k][i]:+.2f}" for k in list(SIG)[:4])
                  + f"   next 60d gold-FI {X60[i]:+.0f}%")


if __name__ == "__main__":
    main()
