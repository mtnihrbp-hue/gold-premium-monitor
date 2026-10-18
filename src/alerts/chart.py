"""The analyst's chart (SP-D, SP_D_HANDOFF.md section 11): 18K's daily candles with EMA20 and
EMA50, the support and resistance levels the analyst computed, the volume profile's value
area where volume exists, the paper account's trades, and today's live price.

DRAFT for the owner's review: not sent by any message until its layout is approved.
Rendered with matplotlib's Agg backend (no display), returned as PNG bytes for Telegram's
sendPhoto. Prices in M toman, as every message shows them.
"""

import io

import numpy as np

RIAL_PER_M_TOMAN = 1e7
COLORS = {"up": "#2e7d32", "down": "#c62828", "ema20": "#1565c0", "ema50": "#ef6c00", "support": "#2e7d32",
          "resistance": "#c62828", "value_area": "#9e9e9e", "live": "#6a1b9a", "grid": "#e0e0e0", "fib": "#8d6e63",
          "pattern": "#00838f", "target": "#00838f"}


def render(dates, opens, highs, lows, closes, ema20=None, ema50=None, supports=(), resistances=(),
           value_area=None, trades=(), live=None, title="18K", days=120, trend=None, fib=(), project=10,
           patterns=None):
    """PNG bytes. `supports`/`resistances`: prices (rial); `value_area`: {"val","vah","poc"};
    `trades`: (date, "BUY"|"SELL", price); `live`: today's price, drawn after the last candle;
    `trend`: caluclator.technical.trendlines() on the same arrays, drawn from their first
    swing and projected `project` days ahead (dotted); `fib`: [(ratio, price)] retracements."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    k = max(0, len(closes) - days)
    o, h, l, c = (np.asarray(x[k:], dtype=float) / RIAL_PER_M_TOMAN for x in (opens, highs, lows, closes))
    ds = list(dates[k:])
    x = np.arange(len(c))
    fig, ax = plt.subplots(figsize=(9, 5.2), dpi=110)
    ax.set_facecolor("white")
    ax.grid(True, color=COLORS["grid"], linewidth=0.6)
    for i in range(len(c)):
        color = COLORS["up"] if c[i] >= o[i] else COLORS["down"]
        ax.vlines(x[i], l[i], h[i], color=color, linewidth=0.8)
        lo_body, hi_body = sorted((o[i], c[i]))
        ax.add_patch(plt.Rectangle((x[i] - 0.35, lo_body), 0.7, max(hi_body - lo_body, 1e-3),
                                   facecolor=color, edgecolor=color, linewidth=0.5))
    if ema20 is not None:
        ax.plot(x, np.asarray(ema20[k:]) / RIAL_PER_M_TOMAN, color=COLORS["ema20"], linewidth=1.2, label="EMA20")
    if ema50 is not None:
        ax.plot(x, np.asarray(ema50[k:]) / RIAL_PER_M_TOMAN, color=COLORS["ema50"], linewidth=1.2, label="EMA50")
    if value_area:
        ax.axhspan(value_area["val"] / RIAL_PER_M_TOMAN, value_area["vah"] / RIAL_PER_M_TOMAN,
                   color=COLORS["value_area"], alpha=0.12, label="value area (volume)")
        ax.axhline(value_area["poc"] / RIAL_PER_M_TOMAN, color=COLORS["value_area"], linewidth=0.8, linestyle=":")
    last = len(c) - 1
    for kind, line in (trend or {}).items():
        if not line:
            continue
        # the most-touched resistance line beside the closest, thin and dashed (owner, 2026-10-18: option C)
        tested = kind == "resistance_tested"
        color = COLORS["resistance" if tested else kind]
        label = f"longer resistance line, touched {line['touches']} times" if tested else f"{kind} trend line"
        slope = (line["y2"] - line["y1"]) / (line["i2"] - line["i1"])
        start = max(line["i1"], k)
        xs = np.arange(start, k + last + 1)
        ys = (line["y1"] + slope * (xs - line["i1"])) / RIAL_PER_M_TOMAN
        ax.plot(xs - k, ys, color=color, linewidth=0.9 if tested else 1.4, linestyle="--" if tested else "-",
                alpha=0.75 if tested else 1.0, label=label)
        ahead = np.array([k + last, k + last + project])
        ya = (line["y1"] + slope * (ahead - line["i1"])) / RIAL_PER_M_TOMAN
        ax.plot(ahead - k, ya, color=color, linewidth=1.2, linestyle=":")
        ax.text(last + project + 0.3, ya[-1], f"{ya[-1]:.2f}", color=color, fontsize=7, va="center")
    for ratio, price in fib:
        y = price / RIAL_PER_M_TOMAN
        ax.axhline(y, color=COLORS["fib"], linewidth=0.7, linestyle=(0, (1, 3)), alpha=0.9)
        ax.text(0.5, y, f"Fib {ratio * 100:.1f}% {y:.2f}", color=COLORS["fib"], fontsize=7, va="bottom")
    right = len(c) + 1.5
    for price, kind in [(p, "support") for p in supports] + [(p, "resistance") for p in resistances]:
        y = price / RIAL_PER_M_TOMAN
        ax.axhline(y, color=COLORS[kind], linewidth=0.9, linestyle="--", alpha=0.8)
        ax.text(right, y, f"{y:.2f}", color=COLORS[kind], fontsize=8, va="center")
    index = {d: i for i, d in enumerate(ds)}
    for day, action, price in trades:
        if day in index:
            ax.annotate("B" if action == "BUY" else "S", (index[day], price / RIAL_PER_M_TOMAN),
                        color="white", fontsize=7, ha="center", va="center", fontweight="bold",
                        bbox=dict(boxstyle="circle,pad=0.25", fc=COLORS["up"] if action == "BUY" else COLORS["down"],
                                  ec="none"))
    # the chart reader's findings (SP_D_HANDOFF.md section 37.4): ranges as boxes, events as markers,
    # a live pattern's measured target as a dotted line; nothing is drawn unless passed
    pat = patterns or {}
    for start, end, lo, hi, label in pat.get("boxes", ()):
        if end < ds[0]:
            continue
        x0 = index.get(start, 0) if start >= ds[0] else 0
        x1 = index.get(end, len(c) - 1)
        ax.add_patch(plt.Rectangle((x0 - 0.5, lo / RIAL_PER_M_TOMAN), x1 - x0 + 1, (hi - lo) / RIAL_PER_M_TOMAN,
                                   facecolor=COLORS["pattern"], alpha=0.10, edgecolor=COLORS["pattern"], linewidth=0.9))
        ax.text(x0, hi / RIAL_PER_M_TOMAN, label, color=COLORS["pattern"], fontsize=7, va="bottom")
    for day, price, label in pat.get("marks", ()):
        if day in index:
            ax.annotate(label, (index[day], price / RIAL_PER_M_TOMAN), xytext=(0, -16), textcoords="offset points",
                        color=COLORS["pattern"], fontsize=7, ha="center",
                        arrowprops=dict(arrowstyle="->", color=COLORS["pattern"], lw=0.8))
    for price, label in pat.get("targets", ()):
        y = price / RIAL_PER_M_TOMAN
        ax.axhline(y, color=COLORS["target"], linewidth=0.9, linestyle=(0, (4, 3)))
        ax.text(len(c) + 1.5, y, f"{y:.2f} {label}", color=COLORS["target"], fontsize=7, va="center")
    if live:
        y = live / RIAL_PER_M_TOMAN
        ax.scatter([len(c)], [y], color=COLORS["live"], s=28, zorder=5)
        ax.text(len(c) + 0.6, y, f" now {y:.2f}", color=COLORS["live"], fontsize=8, va="center", fontweight="bold")
    ticks = list(range(0, len(c), max(1, len(c) // 6)))
    ax.set_xticks(ticks)
    ax.set_xticklabels([ds[t].strftime("%m-%d") for t in ticks], fontsize=8)
    ax.set_xlim(-1, len(c) + 13)
    ax.tick_params(axis="y", labelsize=8)
    ax.set_ylabel("M toman", fontsize=8)
    ax.set_title(title, fontsize=10, loc="left")
    ax.legend(loc="upper left", fontsize=7, frameon=False)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return buf.getvalue()
