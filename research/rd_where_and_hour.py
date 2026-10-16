"""WHERE and the hour: what a buyer saves by choosing the platform, and whether the time of day matters
(SP-D, SP_D_HANDOFF.md section 40; the owner, 2026-10-16: "R&D models, build scenarios").

Rules, fixed before the run:
- Data: research/data/hourly.json, 2026-08-04 to 10-04 (the readings with three platforms or more).
- WHERE, per reading:
    the cheapest platform against the median platform, and against the mean of all
    the mean of the three cheapest (UPDATE's basis) against the cheapest
    a reader loyal to one platform: each platform against the cheapest, how often it is the cheapest
  reported as the mean and median over readings, and per Tehran day (each day's mean) so busy days do
  not count twice. The platforms' price sides are mixed (37.7), so this is the spread a reader sees,
  not a fee-adjusted cost.
- THE HOUR: each reading's basis against the same Tehran day's mean basis, grouped by its Tehran hour
  (06-09, 10-12, 13-15, 16-18, 19-21); and the morning's first reading against the evening's last, per
  day with both. Days are the unit; a bucket with fewer than 15 days is reported as too few.
- Verdict, decided now: an hour "pays" when its days' mean is at least 0.2% below the day's mean, on 15
  days or more, and below it on at least 60% of them. Otherwise none is claimed.

Run: python research/rd_where_and_hour.py
"""

import json
import os
from collections import defaultdict
from datetime import datetime, timedelta
from statistics import mean, median

HERE = os.path.dirname(os.path.abspath(__file__))
TEHRAN = timedelta(hours=3, minutes=30)
BUCKETS = (("06-09", 6, 9), ("10-12", 10, 12), ("13-15", 13, 15), ("16-18", 16, 18), ("19-21", 19, 21))
MIN_DAYS = 15


def load():
    rows = json.load(open(os.path.join(HERE, "data", "hourly.json"), encoding="utf-8"))
    out = []
    for r in rows:
        prices = {k: float(v) for k, v in r["prices"].items() if v}
        if len(prices) < 3:
            continue
        local = datetime.fromisoformat(r["ts"]) + TEHRAN
        ordered = sorted(prices.values())
        out.append({"local": local, "day": local.date(), "prices": prices, "cheapest": ordered[0],
                    "median": median(ordered), "mean": mean(ordered), "basis": mean(ordered[:3])})
    return sorted(out, key=lambda r: r["local"])


def by_day(rows, value):
    days = defaultdict(list)
    for r in rows:
        days[r["day"]].append(value(r))
    return [mean(v) for v in days.values()]


def main():
    rows = load()
    print(f"{len(rows)} readings, {len({r['day'] for r in rows})} days, {rows[0]['day']} .. {rows[-1]['day']}")

    print("\nWHERE (percent above the cheapest platform)")
    for label, f in (("the median platform", lambda r: r["median"] / r["cheapest"] - 1),
                     ("the mean of all", lambda r: r["mean"] / r["cheapest"] - 1),
                     ("the basis (three cheapest)", lambda r: r["basis"] / r["cheapest"] - 1)):
        per_reading = [f(r) * 100 for r in rows]
        per_day = [x * 100 for x in by_day(rows, f)]
        print(f"  {label:<28} readings mean {mean(per_reading):.2f}% median {median(per_reading):.2f}%; "
              f"days mean {mean(per_day):.2f}%")
    platforms = sorted({p for r in rows for p in r["prices"]})
    print("\n  a reader loyal to one platform:")
    for p in platforms:
        seen = [r for r in rows if p in r["prices"]]
        if len(seen) < 50:
            continue
        above = [(r["prices"][p] / r["cheapest"] - 1) * 100 for r in seen]
        cheapest = sum(r["prices"][p] == r["cheapest"] for r in seen) / len(seen)
        print(f"    {p:<10} in {len(seen):>3} readings: {mean(above):.2f}% above the cheapest on average; "
              f"the cheapest in {cheapest:.0%}")

    print("\nTHE HOUR (basis against the same day's mean)")
    day_mean = {d: mean(r["basis"] for r in rows if r["day"] == d) for d in {r["day"] for r in rows}}
    verdicts = {}
    for label, lo, hi in BUCKETS:
        per_day = defaultdict(list)
        for r in rows:
            if lo <= r["local"].hour <= hi:
                per_day[r["day"]].append((r["basis"] / day_mean[r["day"]] - 1) * 100)
        values = [mean(v) for v in per_day.values()]
        if len(values) < MIN_DAYS:
            print(f"  {label}  {len(values)} days: too few")
            verdicts[label] = "too few days"
            continue
        below = sum(v < 0 for v in values) / len(values)
        print(f"  {label}  {len(values):>2} days: mean {mean(values):+.2f}%, median {median(values):+.2f}%, below the day's mean on {below:.0%}")
        verdicts[label] = ("PAYS" if mean(values) <= -0.2 and below >= 0.6 else "no edge")
    pairs = []
    for d in sorted(day_mean):
        today = [r for r in rows if r["day"] == d]
        morning = [r for r in today if r["local"].hour <= 9]
        evening = [r for r in today if r["local"].hour >= 19]
        if morning and evening:
            pairs.append((evening[-1]["basis"] / morning[0]["basis"] - 1) * 100)
    if pairs:
        print(f"\n  the evening's last against the morning's first: {len(pairs)} days, mean {mean(pairs):+.2f}%, "
              f"median {median(pairs):+.2f}%, higher in the evening on {sum(p > 0 for p in pairs) / len(pairs):.0%}")
    print("\nverdicts (decided before the run):")
    for label, v in verdicts.items():
        print(f"  {label}  {v}")


if __name__ == "__main__":
    main()
