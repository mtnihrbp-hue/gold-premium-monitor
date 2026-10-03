"""Does a mature rally predict its end? Causal ZigZag legs (SP-D research, SP_D_HANDOFF.md section 4).

At day i the open rally began at the last trough CONFIRMED by day i (the price had risen
REVERSAL above it by then). Its gain is ranked against rallies completed before day i.
"""
import json, os
from datetime import date
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
rows = json.load(open(os.path.join(HERE, "data", "tgju_history.json")))["geram18"]
d = [date.fromisoformat(r["date"]) for r in rows]; c = np.array([float(r["close"]) for r in rows]); n = len(c)
R = 0.08
# causal zigzag state at every day
state, extreme, last_pivot = "up", 0, 0
leg_start = np.zeros(n, int); leg_dir = np.empty(n, object); completed = []   # (end_day_confirmed, gain)
for i in range(n):
    if state == "up":
        if c[i] > c[extreme]: extreme = i
        elif c[i] <= c[extreme] * (1 - R):
            completed.append((i, (c[extreme] / c[last_pivot] - 1) * 100))   # rally confirmed ended today
            last_pivot, extreme, state = extreme, i, "down"
    else:
        if c[i] < c[extreme]: extreme = i
        elif c[i] >= c[extreme] * (1 + R):
            last_pivot, extreme, state = extreme, i, "up"
    leg_start[i], leg_dir[i] = last_pivot, state
fwd = np.full(n, np.nan); fwd[:n - 20] = (c[20:] / c[:n - 20] - 1) * 100
corr = np.full(n, np.nan)
for i in range(n - 20):
    corr[i] = float(c[i + 1:i + 21].min() / c[i:i + 1].max() - 1 <= -R)   # the rally ends (8% off) within 20d
base_mask = np.array([x.year >= 2016 for x in d]) & ~np.isnan(fwd)
rows_out = []
for i in np.nonzero(base_mask)[0]:
    if leg_dir[i] != "up": continue
    past = [g for day, g in completed if day < i]
    if len(past) < 10: continue
    gain = (c[i] / c[leg_start[i]] - 1) * 100
    rows_out.append((sum(g < gain for g in past) / len(past) * 100, fwd[i], corr[i]))
rows_out = np.array(rows_out)
print(f"days inside a rally, 2016-2026: {len(rows_out)}; all days: 20d median {np.median(fwd[base_mask]):+.1f}%, "
      f"rally ends (8% off) within 20d {np.nanmean(corr[base_mask]) * 100:.0f}%")
print("rally gain so far, ranked against past rallies -> next 20 trading days")
for lo, hi in ((0, 25), (25, 50), (50, 75), (75, 90), (90, 101)):
    sel = rows_out[(rows_out[:, 0] >= lo) & (rows_out[:, 0] < hi)]
    if len(sel):
        print(f"  {lo:3}-{min(hi, 100):3}th pct  {len(sel):4} days   higher {np.mean(sel[:, 1] > 0) * 100:3.0f}%   "
              f"median {np.median(sel[:, 1]):+5.1f}%   rally ended within 20d {np.mean(sel[:, 2]) * 100:3.0f}%")
for split in (date(2023, 12, 31),):
    for label, cond in (("2016-2023", lambda x: x <= split), ("2024-2026", lambda x: x > split)):
        pass
