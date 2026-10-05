"""The chartist, tested (SP-D, 2026-10-05). research/chartist.py reads; this measures.

1. What it read through the 1405 channel and the jump, for the owner's eye.
2. Each finding as an event (its first day in a run): gold's return over fixed income in the
   next 20 and 60 trading days (rd_rebuy.py's target), against all days, in 2016-2020,
   2021-2026 and the last two years (2024-10-05 -> 2026-10-01).
3. The view (its score, fixed before testing): rank correlation with the same target, a
   circular-shift bootstrap for luck, and gold over fixed income by the view's sign.
"""
from collections import Counter, defaultdict
from datetime import date

import numpy as np
from scipy.stats import rankdata

from chartist import Chartist
from rd_rebuy import X20, X60, c, d, flat, h, l, n, rows

ch = Chartist(h, l, c, usable=~flat)
FIRST = next(i for i in range(n) if d[i] >= date(2015, 1, 1))
R = [None] * n
for i in range(FIRST, n):
    R[i] = ch.read(i)
SCORE = np.array([R[i]["score"] if R[i] and R[i]["structure"] else np.nan for i in range(n)])

per_year = Counter(d[s[1]].year for s in ch.swings)
print("swings confirmed per year: " + ", ".join(f"{y}: {per_year[y]}" for y in sorted(per_year) if y >= 2015))

print("\n1. THE 1405 CHANNEL AND THE JUMP, as the chartist read it (every 5th trading day, and every pattern day)")
for i in range(n):
    if d[i] < date(2026, 1, 20) or not R[i] or not R[i]["structure"]:
        continue
    r = R[i]
    prev = R[i - 1] if R[i - 1] else {"patterns": [], "phase": None}
    if i % 10 and set(r["patterns"]) == set(prev["patterns"]) and r["phase"] == prev["phase"]:
        continue
    chn = r["channel"]
    print(f"   {rows[i]['jdate']} {c[i] / 1e7:5.2f}M  {r['structure']:11} {r['phase']:12} channel {chn['slope_pct_day']:+.2f}%/d "
          f"pos {chn['position']:.2f} ({chn['days']}d)  box {r['box'][0] / 1e7:.1f}-{r['box'][1] / 1e7:.1f}  "
          f"{', '.join(r['patterns']) or '-':28} score {r['score']:+.2f}")

SPANS = (("2016-2020", date(2016, 1, 1), date(2020, 12, 31)), ("2021-2026", date(2021, 1, 1), date(2026, 12, 31)),
         ("last 2 years", date(2024, 10, 5), date(2026, 10, 1)))
mask = {k: np.array([lo <= x <= hi for x in d]) for k, lo, hi in SPANS}

print("\n2. EACH FINDING: gold over fixed income in the next 20 / 60 days after its first day (all days in brackets)")
events = defaultdict(list)
for i in range(FIRST + 1, n):
    if not R[i] or not R[i]["structure"]:
        continue
    prev = set(R[i - 1]["patterns"]) if R[i - 1] else set()
    for p in R[i]["patterns"]:
        if p not in prev:
            events[p].append(i)
    if not R[i - 1] or R[i - 1]["phase"] != R[i]["phase"]:
        events["phase " + R[i]["phase"]].append(i)
base = {k: (np.nanmean(X20[m]), np.nanmean(X60[m])) for k, m in mask.items()}
print("   " + " " * 22 + "".join(f"{k:>34}" for k in mask))
print("   " + "all days".ljust(22) + "".join(f"{f'{b[0]:+.2f} / {b[1]:+.2f}':>34}" for b in base.values()))
for name in sorted(events, key=lambda x: (not x.startswith("phase"), x)):
    cells = []
    for k, m in mask.items():
        ev = [i for i in events[name] if m[i]]
        a, b = [X20[i] for i in ev if np.isfinite(X20[i])], [X60[i] for i in ev if np.isfinite(X60[i])]
        cells.append(f"{len(ev):4}: {np.mean(a) if a else np.nan:+6.2f} / {np.mean(b) if b else np.nan:+6.2f}")
    print(f"   {name:22}" + "".join(f"{x:>34}" for x in cells))

print("\n   while in each phase (every day): gold over fixed income, next 20 / 60 days")
for ph in ("MARKUP", "MARKDOWN", "ACCUMULATION", "DISTRIBUTION", "TRANSITION"):
    cells = []
    for k, m in mask.items():
        sel = [i for i in range(n) if m[i] and R[i] and R[i]["phase"] == ph]
        a, b = X20[sel], X60[sel]
        cells.append(f"{len(sel):4}d: {np.nanmean(a):+6.2f} / {np.nanmean(b):+6.2f}")
    print(f"   {ph:22}" + "".join(f"{x:>34}" for x in cells))

rng = np.random.default_rng(3)
print("\n3. THE VIEW (score): rank correlation with gold over fixed income, and luck (circular shift)")
for k, m in mask.items():
    for hz, y in (("20d", X20), ("60d", X60)):
        ok = m & np.isfinite(SCORE) & np.isfinite(y)
        a, b = rankdata(SCORE[ok]), rankdata(y[ok])
        v = np.corrcoef(a, b)[0, 1]
        null = [np.corrcoef(np.roll(a, rng.integers(60, ok.sum() - 60)), b)[0, 1] for _ in range(400)]
        pos, neg, zero = SCORE[ok] > 0, SCORE[ok] < 0, SCORE[ok] == 0
        print(f"   {k:12} {hz}: IC {v:+.2f} (luck {np.mean(np.abs(null) >= abs(v)) * 100:3.0f}%)   gold over fixed income when the "
              f"view is for gold {np.mean(y[ok][pos]):+6.2f}% ({pos.mean() * 100:.0f}% of days), neutral {np.mean(y[ok][zero]) if zero.any() else np.nan:+6.2f}%, "
              f"against gold {np.mean(y[ok][neg]) if neg.any() else np.nan:+6.2f}% ({neg.mean() * 100:.0f}% of days)")
