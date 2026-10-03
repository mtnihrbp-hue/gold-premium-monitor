"""Walk-forward check of the Direction odds and the entry-timing rule (research, read-only).

Each day i is judged with only what was known on day i: similar past cases whose outcome
had already happened (j + h <= i). Compared with what happened next, against the plain
base rate. Brier score: lower is better; a conditional forecast that does not beat the
base rate adds nothing.
"""
import json
import os
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
DATA = json.load(open(os.path.join(HERE, "data", "tgju_history.json")))
from collections import defaultdict

from caluclator.technical import moving_averages, stretch_pct, trend_state
from analysis.direction import MIN_CASES, stretch_band

rows = [(date.fromisoformat(r["date"]), r["close"]) for r in DATA["geram18"]]
dates = [r[0] for r in rows]
close = [float(r[1]) for r in rows]
n = len(close)
avg = moving_averages(close)                      # a simple average at j uses only days <= j
state = [trend_state(close, avg, j) for j in range(n)]
band = [stretch_band(stretch_pct(close, avg, j)) for j in range(n)]
H = 20
START_YEAR = 2016


def walk(event):
    """event(j) -> bool, known at j + H. Returns per-day (year, p_cond, p_base, y)."""
    by_key, by_state, base = defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0]), [0, 0]
    out = []
    for i in range(n):
        j = i - H                                   # this case's outcome became known today
        if j >= 0 and state[j] is not None:
            y = event(j)
            for bucket in (by_key[(state[j], band[j])], by_state[state[j]], base):
                bucket[0] += 1
                bucket[1] += y
        if state[i] is None or i + H >= n or dates[i].year < START_YEAR:
            continue
        k = by_key[(state[i], band[i])]
        if k[0] < MIN_CASES:
            k = by_state[state[i]]
        if k[0] < MIN_CASES or base[0] < MIN_CASES:
            continue
        out.append((dates[i].year, k[1] / k[0], base[1] / base[0], event(i)))
    return out


def report(name, out):
    print(f"\n== {name}: {len(out)} days judged, {START_YEAR}-{dates[-1 - H].year}")
    print("  year   days   happened   Brier conditional   Brier base rate   better?")
    years = sorted({o[0] for o in out})
    total_c = total_b = 0.0
    for year in years:
        rows_y = [o for o in out if o[0] == year]
        bc = sum((p - y) ** 2 for _, p, _, y in rows_y) / len(rows_y)
        bb = sum((b - y) ** 2 for _, _, b, y in rows_y) / len(rows_y)
        total_c += bc * len(rows_y)
        total_b += bb * len(rows_y)
        print(f"  {year}   {len(rows_y):4}   {sum(o[3] for o in rows_y) / len(rows_y) * 100:5.0f}%"
              f"        {bc:.3f}              {bb:.3f}          {'yes' if bc < bb else 'no'}")
    print(f"  all    {len(out):4}                {total_c / len(out):.3f}              {total_b / len(out):.3f}"
          f"          {'yes' if total_c < total_b else 'no'}  "
          f"(skill {(1 - total_c / total_b) * 100:+.1f}%)")
    print("  calibration: forecast band -> how often it happened")
    for lo in (0.0, 0.4, 0.5, 0.6, 0.7, 0.8):
        hi = lo + (0.4 if lo == 0.0 else 0.1) if lo < 0.8 else 1.01
        sel = [o for o in out if lo <= o[1] < hi]
        if sel:
            print(f"    {lo * 100:3.0f}-{min(hi, 1) * 100:3.0f}%  {len(sel):4} days  happened {sum(o[3] for o in sel) / len(sel) * 100:4.0f}%")


report("Higher 20 trading days later", walk(lambda j: close[j + H] > close[j]))
report("Fell 5% or more within 20 days", walk(lambda j: min(close[j + 1:j + H + 1]) / close[j] - 1 <= -0.05))


def paid(j, dip):
    """Price paid relative to converting at once, waiting up to H days for `dip`."""
    target = close[j] * (1 - dip / 100)
    return -dip if any(close[k] <= target for k in range(j + 1, j + H + 1)) else (close[j + H] / close[j] - 1) * 100

print("\n== Entry timing, judged as the system would have: wait for a 3% dip only where the")
print("   past record (outcomes known by that day) said waiting saved money; else convert at once.")
by_key, by_state = defaultdict(lambda: [0, 0.0]), defaultdict(lambda: [0, 0.0])
result = defaultdict(lambda: {"rule": [], "always_wait": [], "days": 0, "waited": 0})
for i in range(n):
    j = i - H
    if j >= 0 and state[j] is not None:
        v = paid(j, 3.0)
        for bucket in (by_key[(state[j], band[j])], by_state[state[j]]):
            bucket[0] += 1
            bucket[1] += v
    if state[i] is None or i + H >= n or dates[i].year < START_YEAR:
        continue
    k = by_key[(state[i], band[i])]
    if k[0] < MIN_CASES:
        k = by_state[state[i]]
    if k[0] < MIN_CASES:
        continue
    wait = k[1] / k[0] < 0                          # waiting paid less on average in the past
    v = paid(i, 3.0)
    r = result[dates[i].year]
    r["days"] += 1
    r["waited"] += wait
    r["rule"].append(v if wait else 0.0)
    r["always_wait"].append(v)
print("  year   days  rule waited   rule vs converting at once   always waiting vs at once")
tot = {"rule": [], "always_wait": []}
for year in sorted(result):
    r = result[year]
    tot["rule"] += r["rule"]; tot["always_wait"] += r["always_wait"]
    print(f"  {year}   {r['days']:4}   {r['waited'] / r['days'] * 100:4.0f}%          "
          f"{sum(r['rule']) / len(r['rule']):+6.2f}%                     {sum(r['always_wait']) / len(r['always_wait']):+6.2f}%")
print(f"  all    {len(tot['rule']):4}                 {sum(tot['rule']) / len(tot['rule']):+6.2f}%"
      f"                     {sum(tot['always_wait']) / len(tot['always_wait']):+6.2f}%")
print("  (negative = paid less than converting at once on the same day)")
