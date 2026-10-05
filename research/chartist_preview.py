"""A picture of what the chartist sees on the last day (research only; the 21:00 chart is unchanged)."""
import os

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from chartist import Chartist  # noqa: E402
from rd_rebuy import c, flat, h, l, n, o, rows  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ch = Chartist(h, l, c, usable=~flat)
i = n - 1
r = ch.read(i)
k = n - 200
x = np.arange(200)
M = 1e7
fig, ax = plt.subplots(figsize=(10, 5.6), dpi=110)
for j in range(k, n):
    col = "#2e7d32" if c[j] >= o[j] else "#c62828"
    lo_, hi_ = (min(l[j], c[j], o[j]), max(h[j], c[j], o[j])) if not flat[j] else (c[j], c[j])
    ax.vlines(j - k, lo_ / M, hi_ / M, color=col, linewidth=0.7)
    b0, b1 = sorted((o[j], c[j]))
    ax.add_patch(plt.Rectangle((j - k - 0.35, b0 / M), 0.7, max(b1 - b0, 1e3) / M, color=col, linewidth=0))
sw = [s for s in ch.known(i) if s[1] >= k]
ax.plot([s[1] - k for s in sw], [s[2] / M for s in sw], color="#455a64", linewidth=1.0, linestyle="-", alpha=0.7,
        label="swings (confirmed)")
for s in sw:
    ax.annotate("H" if s[3] == "H" else "L", (s[1] - k, s[2] / M), textcoords="offset points",
                xytext=(0, 7 if s[3] == "H" else -12), ha="center", fontsize=7, color="#455a64", fontweight="bold")
chn = r["channel"]
days = chn["days"]
y = np.log(c[i - days + 1:i + 1])
xx = np.arange(days)
slope, icpt = np.polyfit(xx, y, 1)
sd = (y - (icpt + slope * xx)).std()
xs = np.arange(i - days + 1, i + 1) - k
for off, sty in ((0, "--"), (2 * sd, "-"), (-2 * sd, "-")):
    ax.plot(xs, np.exp(icpt + slope * xx + off) / M, color="#1565c0", linewidth=1.1, linestyle=sty,
            label="channel" if off == 2 * sd else None)
if r.get("box"):
    b_lo, b_hi = r["box"]
    ax.axhspan(b_lo / M, b_hi / M, color="#ffb300", alpha=0.10, label="box (last two swing highs and lows)")
ax.text(0.01, 0.97, f"{rows[i]['jdate']}  structure {r['structure']}  phase {r['phase']}", transform=ax.transAxes,
        fontsize=9, va="top", fontweight="bold")
ax.text(0.01, 0.92, f"patterns: {', '.join(r['patterns']) or 'none'}   channel {chn['slope_pct_day']:+.2f}% a day, "
        f"price at {chn['position']:.2f} of it   view {r['score']:+.2f}", transform=ax.transAxes, fontsize=8, va="top")
ticks = list(range(0, 200, 25))
ax.set_xticks(ticks)
ax.set_xticklabels([rows[k + t]["jdate"][2:] for t in ticks], fontsize=7)
ax.set_ylabel("M toman", fontsize=8)
ax.grid(True, color="#eeeeee", linewidth=0.6)
ax.legend(loc="lower right", fontsize=7, frameon=False)
ax.set_title("What the chartist sees: 18K, the last 200 trading days", fontsize=10, loc="left")
fig.tight_layout()
out = os.path.join(HERE, "data", "chartist_preview.png")
fig.savefig(out)
print(out)
