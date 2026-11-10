"""The funds' line issued on a week's third session against the record's whole week (SP_D_HANDOFF.md 111.2).

    python research/rd_fund_line_third_session.py
"""
import bisect
import json
import math
import os
import sys
from collections import Counter
from datetime import timedelta

os.environ["DATABASE_URL"] = "postgresql://x@127.0.0.1:1/x"
sys.path.insert(0, "research")
sys.stdout.reconfigure(encoding="utf-8")
import rd_fund_week_classes as m  # noqa: E402

flows = m.daily_flows()
ds, vs = m.closes()
calm = json.load(open("research/data/calm_forecasts_b.json", encoding="utf-8"))
week = lambda d: d - timedelta(days=(d.weekday() - 5) % 7)
weeks = {}
for d in sorted(flows):
    weeks.setdefault(week(d), []).append(d)


def power(days):
    bv, bc, sv, sc = (sum(flows[d][k] for d in days) for k in range(4))
    return (bv / bc) / (sv / sc) if bv and bc and sv and sc else None


full = [w for w in sorted(weeks) if len(weeks[w]) >= 3 and power(weeks[w])]
zone = lambda r: None if r is None else "SELLERS" if r < 40 else "BUYERS" if r < 80 else "CROWDED"
sigma = lambda d: math.exp(calm[d.isoformat()]["X"]) if d.isoformat() in calm and calm[d.isoformat()].get("X") is not None else None


def outcome(day):
    """From `day`'s close over the next 7 calendar days: closed lower, reached the low edge, reached the high edge."""
    c0 = m.on_or_before(ds, vs, day)
    if not c0 or day + timedelta(days=7) > ds[-1]:
        return None
    i0 = bisect.bisect_right(ds, day)
    nxt = [vs[j] for j in range(i0, len(ds)) if ds[j] <= day + timedelta(days=7)]
    k = bisect.bisect_right(ds, day) - 1
    s = sigma(ds[k]) if k >= 0 else None
    if not nxt or not s:
        return None
    lo = min(math.log(v / c0) for v in nxt)
    hi = max(math.log(v / c0) for v in nxt)
    return {"lower": nxt[-1] < c0, "drop": lo <= -1.11 * s * math.sqrt(3), "rise": hi >= 1.89 * s * math.sqrt(3)}


rows = []
for i, w in enumerate(full):
    days = weeks[w]
    hist = [power(weeks[x]) for x in full[max(0, i - 52):i]]
    z_full = zone(m.rank(hist, power(days)))
    z_3 = zone(m.rank(hist, power(days[:3]))) if len(days) >= 4 and power(days[:3]) else None
    rows.append({"w": w, "n": len(days), "z_full": z_full, "z_3": z_3, "end": outcome(days[-1]), "third": outcome(days[2])})

ranked = [r for r in rows if r["z_full"]]
both = [r for r in ranked if r["z_3"]]
print("weeks ranked", len(ranked), "| with 4+ sessions and a zone at the third", len(both), "| sessions per week", dict(Counter(r["n"] for r in ranked)))
same = sum(r["z_full"] == r["z_3"] for r in both)
print(f"the zone after 3 sessions equals the whole week's: {same} of {len(both)} = {100 * same / len(both):.0f}%")
for z in ("SELLERS", "BUYERS", "CROWDED"):
    g = [r for r in both if r["z_3"] == z]
    print(f"   called {z} on the third session: {len(g)}; ended {dict(Counter(r['z_full'] for r in g))}")


def table(label, key, zkey):
    print(f"\n{label}")
    for z in ("SELLERS", "BUYERS", "CROWDED", None):
        g = [r[key] for r in ranked if r[zkey] and (z is None or r[zkey] == z) and r[key]]
        print(f"   {z or 'every':8} n {len(g):3d}  closed lower {100 * sum(x['lower'] for x in g) / len(g):4.0f}%  reached the low edge {100 * sum(x['drop'] for x in g) / len(g):4.0f}%  reached the high edge {100 * sum(x['rise'] for x in g) / len(g):4.0f}%")


table("as the record measured it: the whole week's zone, from the week's last close, 7 days", "end", "z_full")
table("as production issues it on the third session: the zone so far, from that night's close, 7 days", "third", "z_3")
