"""The 3-day floor out of sample, tgju's Thursdays, and the horizon without them (SP_D_HANDOFF.md 111.3).

    python research/rd_floor_walk_forward.py
"""
import json
import math
import statistics as st
import sys
from collections import Counter, defaultdict
from datetime import date

sys.stdout.reconfigure(encoding="utf-8")
rows = json.load(open("research/data/tgju_history.json", encoding="utf-8"))["geram18"]
gold = sorted((date.fromisoformat(r["date"]), float(r["close"])) for r in rows if r.get("close"))
days = [d for d, _ in gold]
close = [c for _, c in gold]
calm = json.load(open("research/data/calm_forecasts_b.json", encoding="utf-8"))
print("tgju rows", len(gold), days[0], "to", days[-1])

names = "Mon Tue Wed Thu Fri Sat Sun".split()
print("\n-- rows by weekday:", {names[k]: v for k, v in sorted(Counter(d.weekday() for d in days).items())})
by_year = defaultdict(Counter)
for d in days:
    by_year[d.year][d.weekday()] += 1
for y in sorted(by_year):
    if y >= 2015:
        print(f"   {y}: Thu {by_year[y][3]:3d}  Fri {by_year[y][4]:3d}  all {sum(by_year[y].values())}")

H = 3
out = []
for i in range(len(gold) - H):
    d = days[i].isoformat()
    x = (calm.get(d) or {}).get("X")
    if x is None or days[i].year < 2018:
        continue
    s = math.exp(x) * math.sqrt(3)
    out.append((days[i], math.log(close[i + H] / close[i]) / s, math.log(close[i + H] / close[i])))
print("\ndays with the calm model's forecast, from 2018:", len(out), out[0][0], "to", out[-1][0])

print("\n-- the floor at -1.11 (the shipped constant) and a higher close, by year")
yr = defaultdict(list)
for d, z, r in out:
    yr[d.year].append((z, r))
for y in sorted(yr):
    v = yr[y]
    print(f"   {y}: n {len(v):3d}  above the floor {100 * sum(z > -1.11 for z, _ in v) / len(v):5.1f}%   higher {100 * sum(r > 0 for _, r in v) / len(v):5.1f}%")
print(f"   all: n {len(out)}  above the floor {100 * sum(z > -1.11 for _, z, _ in out) / len(out):.1f}%   higher {100 * sum(r > 0 for _, _, r in out) / len(out):.1f}%")

print("\n-- walk-forward: the 10% quantile learned on every year before, applied to the next")
total, hits = 0, 0
for y in sorted(yr):
    train = sorted(z for d, z, _ in out if d.year < y)
    if len(train) < 200:
        continue
    q = train[int(len(train) * 0.10)]
    v = yr[y]
    h = sum(z > q for z, _ in v)
    total += len(v)
    hits += h
    print(f"   {y}: learned {q:+.2f}  held {100 * h / len(v):5.1f}%")
print(f"   out of sample, all years: {100 * hits / total:.1f}% of {total}")

recent = [(d, z) for d, z, _ in out if d >= date(2026, 1, 1)]
print(f"\n-- 2026 so far: {len(recent)} days, above the floor {100 * sum(z > -1.11 for _, z in recent) / len(recent):.1f}%")

print("\n-- the horizon if Thursday rows are skipped (the audit's fix): 3 rows that are not Thursdays")
idx = [i for i, d in enumerate(days) if d.weekday() != 3]
alt = []
for j, i in enumerate(idx[:-H]):
    d = days[i].isoformat()
    x = (calm.get(d) or {}).get("X")
    if x is None or days[i].year < 2018:
        continue
    s = math.exp(x) * math.sqrt(3)
    alt.append(math.log(close[idx[j + H]] / close[i]) / s)
print(f"   n {len(alt)}  above the floor {100 * sum(z > -1.11 for z in alt) / len(alt):.1f}%   higher {100 * sum(z > 0 for z in alt) / len(alt):.1f}%")
