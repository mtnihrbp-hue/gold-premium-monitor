"""Extrapolation: where 18K is likely to be in 5, 20 and 60 trading days, and how sure (SP-D, 2026-10-04).

The owner: "something I like to see is extrapolation." And earlier: "how can we lock the
accuracy to +95%?" A direction cannot be called 95% of the time; a band can be built to
hold the future price 95% of the time, and whether it does is measurable. This measures it,
walk-forward on tgju's daily 18K (2016-2026), every band built from the days before only.

The centre line, four ways (the slope it extrapolates, per day, in log terms):
  no change      the price stays where it is
  quant drift    the quant engine's drift (section 12: 18K's two regimes, refitted yearly)
  year's trend   the mean daily move of the last 250 days
  60-day line    the slope of a straight line through the last 60 closes
The width: the EWMA volatility (0.94) times sqrt(days), scaled two ways:
  normal         the bell curve's 80% and 95% points
  own history    the 10/90 and 2.5/97.5% points of 18K's own past standardised moves
                 (filtered historical simulation: fat tails and skew as they happened)

A band is honest when it holds the price as often as it says (80% -> 80%). The centre is
useful when it misses by less than "no change".
"""
import os
from datetime import date

import numpy as np

from rd_rebuy import c, d, n, rows

HERE = os.path.dirname(os.path.abspath(__file__))
lc = np.log(c)
ret = np.concatenate([[0.0], np.diff(lc)])
var = np.zeros(n)
var[0] = np.var(ret[1:60])
for i in range(1, n):
    var[i] = 0.94 * var[i - 1] + 0.06 * ret[i] ** 2
sig = np.sqrt(var)
MU = np.load(os.path.join(HERE, "data", "quant_D.npy"))
FIRST = next(i for i in range(n) if d[i] >= date(2016, 1, 1))

slope60 = np.full(n, np.nan)
x = np.arange(60)
for i in range(60, n):
    slope60[i] = np.polyfit(x, lc[i - 59:i + 1], 1)[0]
trend250 = np.full(n, np.nan)
trend250[250:] = (lc[250:] - lc[:-250]) / 250
CENTRES = {"no change": np.zeros(n), "quant drift": np.nan_to_num(MU, nan=0.0), "year's trend": trend250,
           "60-day line": slope60}
HORIZONS = (5, 20, 60)
PERIODS = (("2016-2020", date(2016, 1, 1), date(2020, 12, 31)), ("2021-2026", date(2021, 1, 1), date(2026, 12, 31)))


def realised(h):
    out = np.full(n, np.nan)
    out[:n - h] = lc[h:] - lc[:n - h]
    return out


R = {h: realised(h) for h in HORIZONS}


def bands(centre, h, method):
    """(low80, high80, low95, high95) in log terms around the centre, for every day."""
    mid = centre * h
    s = sig * np.sqrt(h)
    if method == "normal":
        q = np.array([-1.2816, 1.2816, -1.96, 1.96])
        return [mid + k * s for k in q]
    z = np.where(s > 0, (R[h] - mid) / s, np.nan)       # standardised outcomes, known h days later
    out = [np.full(n, np.nan) for _ in range(4)]
    for i in range(FIRST, n):
        past = z[max(0, i - h - 1500):i - h]
        past = past[np.isfinite(past)]
        if len(past) < 250:
            continue
        q = np.quantile(past, [0.10, 0.90, 0.025, 0.975])
        for k in range(4):
            out[k][i] = mid[i] + q[k] * s[i]
    return out


print("1. DOES THE BAND HOLD THE PRICE AS OFTEN AS IT SAYS? (80% band | 95% band; average width of the 95% band)")
for method in ("normal", "own history"):
    for h in HORIZONS:
        cells = []
        for label, lo, hi in PERIODS:
            sel = np.array([lo <= x_ <= hi for x_ in d]) & np.isfinite(R[h])
            lo80, hi80, lo95, hi95 = bands(CENTRES["quant drift"], h, method)
            ok = sel & np.isfinite(lo95)
            in80 = np.mean((R[h][ok] >= lo80[ok]) & (R[h][ok] <= hi80[ok])) * 100
            in95 = np.mean((R[h][ok] >= lo95[ok]) & (R[h][ok] <= hi95[ok])) * 100
            width = np.mean(np.exp(hi95[ok]) - np.exp(lo95[ok])) * 100
            cells.append(f"{label}: {in80:4.0f}% | {in95:4.0f}%  (+/-{width / 2:4.1f}%)")
        print(f"   {method:11} {h:2} days  " + "     ".join(cells))

print("\n2. THE CENTRE LINE: typical miss (median absolute, %) and how often it had the direction right")
for h in HORIZONS:
    for label, lo, hi in PERIODS:
        sel = np.array([lo <= x_ <= hi for x_ in d]) & np.isfinite(R[h])
        cells = []
        for name, ctr in CENTRES.items():
            ok = sel & np.isfinite(ctr)
            miss = np.median(np.abs(R[h][ok] - ctr[ok] * h)) * 100
            right = np.mean(np.sign(R[h][ok]) == np.sign(ctr[ok] * h)) * 100 if name != "no change" else np.mean(R[h][ok] > 0) * 100
            cells.append(f"{name} {miss:5.1f}% / {right:3.0f}%")
        print(f"   {h:2} days {label}: " + "   ".join(cells))
print("   (for 'no change' the second number is how often 18K was higher: the bar a direction call must beat)")

print("\n3. TODAY'S EXTRAPOLATION (own-history band around the quant drift), from the last close")
i = n - 1
for h in HORIZONS:
    lo80, hi80, lo95, hi95 = (b[i] for b in bands(CENTRES["quant drift"], h, "own history"))
    mid = CENTRES["quant drift"][i] * h
    f = lambda v: np.exp(lc[i] + v) / 1e7
    print(f"   {rows[i]['jdate']} {c[i] / 1e7:.2f}M -> {h:2} trading days: centre {f(mid):.2f}M, 80% between {f(lo80):.2f} and "
          f"{f(hi80):.2f}M, 95% between {f(lo95):.2f} and {f(hi95):.2f}M")

# a preview of the cone on the chart (research only; the 21:00 chart is unchanged)
import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

k = n - 120
fig, ax = plt.subplots(figsize=(9, 5.2), dpi=110)
ax.plot(range(120), c[k:] / 1e7, color="#424242", linewidth=1.3, label="18K close")
ahead = np.arange(0, 61)
cone = {}
for h in range(1, 61):
    s = sig[i] * np.sqrt(h)
    zs = (realised(h) - CENTRES["quant drift"] * h) / (sig * np.sqrt(h))
    past = zs[max(0, i - h - 1500):i - h]
    past = past[np.isfinite(past)]
    q = np.quantile(past, [0.10, 0.90, 0.025, 0.975])
    cone[h] = [np.exp(lc[i] + CENTRES["quant drift"][i] * h + qq * s) / 1e7 for qq in q] + \
              [np.exp(lc[i] + CENTRES["quant drift"][i] * h) / 1e7]
xs = 119 + np.arange(1, 61)
ax.fill_between(xs, [cone[h][2] for h in range(1, 61)], [cone[h][3] for h in range(1, 61)], color="#7e57c2", alpha=0.12,
                label="95% band")
ax.fill_between(xs, [cone[h][0] for h in range(1, 61)], [cone[h][1] for h in range(1, 61)], color="#7e57c2", alpha=0.25,
                label="80% band")
ax.plot(xs, [cone[h][4] for h in range(1, 61)], color="#4527a0", linewidth=1.2, linestyle="--", label="centre (quant drift)")
for h in (20, 60):
    lo95_, hi95_ = cone[h][2], cone[h][3]
    ax.text(119 + h + 0.5, hi95_, f"{hi95_:.1f}", fontsize=7, color="#4527a0")
    ax.text(119 + h + 0.5, lo95_, f"{lo95_:.1f}", fontsize=7, color="#4527a0")
ticks = list(range(0, 120, 20))
ax.set_xticks(ticks + [119 + 20, 119 + 60])
ax.set_xticklabels([rows[k + t]["jdate"][5:] for t in ticks] + ["+20d", "+60d"], fontsize=8)
ax.set_ylabel("M toman", fontsize=8)
ax.set_title(f"18K, the last 120 days and the next 60: extrapolation from {rows[i]['jdate']}", fontsize=10, loc="left")
ax.grid(True, color="#e0e0e0", linewidth=0.6)
ax.legend(loc="upper left", fontsize=7, frameon=False)
fig.tight_layout()
out = os.path.join(HERE, "data", "extrapolation_preview.png")
fig.savefig(out)
print(f"\n   preview: {out}")
