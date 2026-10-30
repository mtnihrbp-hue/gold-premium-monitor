"""E-7, GDELT's coverage added to the risk of a fall (SP_D_HANDOFF.md section 77.6; registered in 8501761 before
this run).

R6 = R3's three inputs (18K's 20-day return, the real dollar against its 5 years, the calm forecast) plus the
coverage jumps of "iran nuclear talks", "iran military" and "iran sanctions": the log of the theme's share of all
coverage over the last 5 GDELT days before t against its last 60. Same target, method and periods as E-5. The
test: R6's Brier score 5% or more below R3's on the same days in 2 of 3 periods.

    python research/rd_fall_risk_news.py
"""

import bisect
import json
import math
import os
import sys
from datetime import date

from sklearn.metrics import roc_auc_score

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rd_fall_risk as e5  # noqa: E402
import rd_windows_read as g4  # noqa: E402

THEMES = {"talks jump": "iran nuclear talks", "military jump": "iran military", "sanctions jump": "iran sanctions"}


def gdelt_jumps():
    with open(os.path.join(HERE, "data", "gdelt.json"), encoding="utf-8") as f:
        raw = json.load(f)
    out = {}
    for name, q in THEMES.items():
        vol = sorted((date(int(d[:4]), int(d[4:6]), int(d[6:])), c / t) for d, c, t in raw[q]["volume"] if t)
        days = [d for d, _ in vol]
        share = [s for _, s in vol]
        out[name] = (days, share)
    return out


def jump_asof(series, day):
    days, share = series
    i = bisect.bisect_left(days, day) - 1          # strictly before the day
    if i < 60:
        return None
    s5 = sum(share[i - 4:i + 1]) / 5
    s60 = sum(share[i - 59:i + 1]) / 60
    return math.log(s5 / s60) if s5 > 0 and s60 > 0 else None


def main():
    with open(os.path.join(HERE, "data", "panel.json"), encoding="utf-8") as f:
        rows = json.load(f)["rows"]
    with open(os.path.join(HERE, "data", "macro.json"), encoding="utf-8") as f:
        macro = json.load(f)
    with open(os.path.join(HERE, "data", "calm_forecasts_b.json"), encoding="utf-8") as f:
        calm = json.load(f)
    F = g4.drivers(rows, macro, calm)
    jumps = gdelt_jumps()
    dates = [date.fromisoformat(r["date"]) for r in rows]
    for i, d in enumerate(dates):
        for name in THEMES:
            F[i][name] = jump_asof(jumps[name], d) if d <= date(2026, 10, 2) else None
    y = e5.target(rows)
    r3 = e5.walk(rows, F, y, e5.R3)
    r6 = e5.walk(rows, F, y, e5.R3 + list(THEMES))
    wins = 0
    for pname, a, b in e5.PERIODS:
        common = [i for i in r6 if i in r3 and a <= dates[i] <= b and y[i] is not None
                  and all(F[i][k] is not None for k in THEMES)]
        b3 = sum((r3[i] - y[i]) ** 2 for i in common) / len(common)
        b6 = sum((r6[i] - y[i]) ** 2 for i in common) / len(common)
        ys = [y[i] for i in common]
        a3 = roc_auc_score(ys, [r3[i] for i in common])
        a6 = roc_auc_score(ys, [r6[i] for i in common])
        gain = 1 - b6 / b3
        wins += gain >= 0.05
        print(f"{pname}: {len(common)} days; Brier R3 {b3:.4f}, R6 {b6:.4f} ({gain:+.1%}); AUC R3 {a3:.2f}, R6 {a6:.2f}")
    print(f"TEST: R6 beats R3 by 5% in {wins} of 3 -> {'PASS' if wins >= 2 else 'no'}")


if __name__ == "__main__":
    main()
