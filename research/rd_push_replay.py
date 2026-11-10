"""Replay of the deep-discount push on WallGold alone, over the stored readings (SP_D_HANDOFF.md 109.7), read-only.

    python research/rd_push_replay.py [--cache path.json]

Same rule as analysis/push_trigger: the 85th percentile of the settled 30 days, re-arm band, armed state.
For each would-be push: WallGold's price then, and WallGold's price at the day's last reading 1, 3 and 7 days on,
and whether the others agreed (the discount of the next-lowest gram platforms at that reading).
"""
import statistics as st
import sys
from collections import defaultdict
from datetime import datetime, timedelta

sys.path.insert(0, "src")
sys.stdout.reconfigure(encoding="utf-8")
from analysis.bubble_position import DEEP_DISCOUNT_PERCENTILE, _value_at_percentile  # noqa: E402

TEHRAN = timedelta(hours=3, minutes=30)
MIN_OBS = 30
sys.path.insert(0, "research")
import rd_discount_basis as basis  # noqa: E402

data = basis.load(sys.argv[sys.argv.index("--cache") + 1] if "--cache" in sys.argv else None)
rows = []
for r in data["readings"]:
    w = r["p"].get("WallGold")
    if not w:
        continue
    t = datetime.fromisoformat(r["t"])
    rows.append({"t": t, "local": t + TEHRAN, "day": (t + TEHRAN).date(), "gap": (w / r["fair"] - 1) * 100, "w": w, "p": r["p"], "fair": r["fair"]})
print(len(rows), "readings with WallGold", rows[0]["local"], "to", rows[-1]["local"])

by_day = defaultdict(list)
for x in rows:
    by_day[x["day"]].append(x)
days = sorted(by_day)


def thresholds(day):
    pool = [x for d in days if day - timedelta(days=30) <= d < day for x in by_day[d]]
    if len(pool) < MIN_OBS:
        return None
    sizes = sorted(-x["gap"] for x in pool if x["gap"] < 0)
    if len(sizes) < MIN_OBS:
        return None
    fire = _value_at_percentile(sizes, DEEP_DISCOUNT_PERCENTILE)
    steps = []
    for a, b in zip(pool, pool[1:]):
        h = (b["t"] - a["t"]).total_seconds() / 3600
        if 0 < h <= 2:
            steps.append(abs(abs(b["gap"]) - abs(a["gap"])))
    steps.sort()
    noise = steps[min(len(steps) - 1, int(len(steps) * 0.9))] if steps else 0
    band = max(0.25, noise * 1.5)
    return fire, max(0.0, fire - band)


def later(day, h):
    """WallGold's last reading h days on (the next day that has one, up to 2 days after)."""
    for extra in range(3):
        d = day + timedelta(days=h + extra)
        if d in by_day:
            return by_day[d][-1]["w"]
    return None


armed = True
fires = []
judged = 0
all_points = []
for day in days:
    th = thresholds(day)
    if th is None:
        continue
    fire, rearm = th
    for x in by_day[day]:
        judged += 1
        size = abs(x["gap"])
        all_points.append((day, x, fire))
        if x["gap"] > 0:
            armed = True
            continue
        if armed and size >= fire:
            others = sorted(v for k, v in x["p"].items() if k != "WallGold" and k in ("Milli", "Goldika", "Ayyareh", "Daric", "Invi"))
            other_low3 = (st.mean(others[:3]) / x["fair"] - 1) * 100 if len(others) >= 3 else None
            fires.append((x, fire, other_low3))
            armed = False
        elif not armed and size < rearm:
            armed = True

print("readings judged", judged, "days", len({d for d, _, _ in all_points}), "from", all_points[0][0])
print("\nwould-be pushes:", len(fires))
print("when (Tehran)      gap   level  others' 3 lowest   +1d    +3d    +7d (WallGold, last reading)")
out = {1: [], 3: [], 7: []}
for x, fire, other in fires:
    row = []
    for h in (1, 3, 7):
        v = later(x["day"], h)
        if v:
            r = (v / x["w"] - 1) * 100
            out[h].append(r)
            row.append(f"{r:+6.2f}")
        else:
            row.append("   n/a")
    print(x["local"].strftime("%m-%d %H:%M"), f"{x['gap']:+6.2f} {fire:6.2f}  {other if other is None else round(other, 2)!s:>8}      ", " ".join(row))

print("\nbaseline: every day's last reading, WallGold h days on")
for h in (1, 3, 7):
    base = []
    for day in days:
        if day < all_points[0][0]:
            continue
        v = later(day, h)
        if v:
            base.append((v / by_day[day][-1]["w"] - 1) * 100)
    f = out[h]
    print(f"h={h}: pushes n={len(f)} typical {st.median(f) if f else float('nan'):+.2f}% up {sum(r > 0 for r in f)}/{len(f)}   "
          f"every day n={len(base)} typical {st.median(base):+.2f}% up {sum(r > 0 for r in base)}/{len(base)}")

print("\nthe discount itself, 3 days on (the day's last reading then, against the gap now): + means it narrowed")
for h in (1, 3, 7):
    def gap_later(day):
        for extra in range(3):
            d = day + timedelta(days=h + extra)
            if d in by_day:
                return by_day[d][-1]["gap"]
        return None
    pushes = [gap_later(x["day"]) - x["gap"] for x, _, _ in fires if gap_later(x["day"]) is not None]
    every = [gap_later(d) - by_day[d][-1]["gap"] for d in days if d >= all_points[0][0] and gap_later(d) is not None]
    print(f"h={h}: pushes n={len(pushes)} typical {st.median(pushes):+.2f} pp, narrowed {sum(p > 0 for p in pushes)}/{len(pushes)}   "
          f"every day n={len(every)} typical {st.median(every):+.2f} pp, narrowed {sum(p > 0 for p in every)}/{len(every)}")

print("\nwhat closed it, 3 days on: WallGold's own move and the world-price-and-dollar (fair) move")
for x, fire, other in fires:
    last = None
    for extra in range(3):
        d = x["day"] + timedelta(days=3 + extra)
        if d in by_day:
            last = by_day[d][-1]
            break
    if last:
        print(x["local"].strftime("%m-%d %H:%M"), f"WallGold {(last['w'] / x['w'] - 1) * 100:+6.2f}%   fair {(last['fair'] / x['fair'] - 1) * 100:+6.2f}%")

clean = [f for f in fires if f[0]["t"] >= datetime(2026, 9, 29)]
print("\nsince 09-29 only:", len(clean), "pushes")
for h in (1, 3, 7):
    r = [(later(x["day"], h) / x["w"] - 1) * 100 for x, _, _ in clean if later(x["day"], h)]
    if r:
        print(f"  h={h}: n={len(r)} typical {st.median(r):+.2f}% up {sum(v > 0 for v in r)}/{len(r)}")
no_second = [f for f in fires if f[2] is not None and -f[2] < f[1]]
print("would not have a second platform group as deep (others' three lowest under the level):", len(no_second), "of", len(fires))

# how long does a deep spell last, and does it narrow
print("\nthe discount the next reading, 3 readings and 8 readings after a push (does it close?)")
index = {id(x): i for i, x in enumerate(rows)}
for x, fire, other in fires:
    i = index[id(x)]
    print(x["local"].strftime("%m-%d %H:%M"), [round(rows[i + k]["gap"], 2) if i + k < len(rows) else None for k in (1, 3, 8)])
