"""Volume profile with real money volume: do 18K's high-volume price zones hold? (SP-D, 2026-10-04)

No platform publishes volume; the gold funds on the Tehran exchange do (TSETMC: value
traded per day, every gold fund summed). Each day's value is spread evenly across that
day's 18K range (tgju low..high), into 1% price bins. Over the last 120 trading days:
the POC (the most traded bin), the value area (the bins holding 70% of the value, from
the POC outward) and HVNs (bins holding 1.5x the average).

Test, as for the swing levels (section 2, R2b): a support "holds" when, within 20 trading
days, 18K never closes 2% or more below it. Compared with a level with no history at the
same distance below the price (0-2%). Resistance, the mirror: never closes 2% above it.
2019-2023 and 2024-2026.
"""
import json
import os
from bisect import bisect_right
from collections import defaultdict
from datetime import date

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
T = json.load(open(os.path.join(HERE, "data", "tgju_history.json")))
F = json.load(open(os.path.join(HERE, "data", "tsetmc_gold_funds.json"), encoding="utf-8"))
NOT_GOLD = {"سافرون"}
rows = T["geram18"]
d = [date.fromisoformat(r["date"]) for r in rows]
c = np.array([float(r["close"]) for r in rows])
h = np.array([float(r["high"]) for r in rows])
l = np.array([float(r["low"]) for r in rows])
n = len(c)
value = defaultdict(float)
for code, f in F.items():
    if f["symbol"] in NOT_GOLD:
        continue
    for p in f["prices"]:
        value[p["date"]] += p["value"]
v = np.array([value.get(x.strftime("%Y%m%d"), 0.0) for x in d])
H, LOOK, STEP = 20, 120, np.log1p(0.01)


def profile(i):
    lo, hi = np.log(l[i - LOOK + 1:i + 1].min()), np.log(h[i - LOOK + 1:i + 1].max())
    edges = np.arange(lo, hi + STEP, STEP)
    mass = np.zeros(len(edges) - 1)
    for j in range(i - LOOK + 1, i + 1):
        if v[j] <= 0:
            continue
        a, b = np.log(min(l[j], c[j])), np.log(max(h[j], c[j]))
        ka, kb = max(0, np.searchsorted(edges, a) - 1), min(len(mass) - 1, np.searchsorted(edges, b) - 1)
        mass[ka:kb + 1] += v[j] / (kb - ka + 1)
    mids = np.exp((edges[:-1] + edges[1:]) / 2)
    return mids, mass


def levels(i):
    mids, mass = profile(i)
    if mass.sum() <= 0:
        return {}
    poc = int(np.argmax(mass))
    order, area, k = [poc], mass[poc], 0
    lo_k, hi_k = poc, poc
    while area < 0.7 * mass.sum():
        down = mass[lo_k - 1] if lo_k > 0 else -1
        up = mass[hi_k + 1] if hi_k < len(mass) - 1 else -1
        if up >= down:
            hi_k += 1
            area += mass[hi_k]
        else:
            lo_k -= 1
            area += mass[lo_k]
    hvn = [mids[k] for k in range(len(mass)) if mass[k] >= 1.5 * mass.mean()
           and (k == 0 or mass[k] >= mass[k - 1]) and (k == len(mass) - 1 or mass[k] >= mass[k + 1])]
    return {"poc": mids[poc], "val": mids[lo_k], "vah": mids[hi_k], "hvn": hvn}


def holds_below(i, level):
    return bool((c[i + 1:i + H + 1] > level * 0.98).all())


def holds_above(i, level):
    return bool((c[i + 1:i + H + 1] < level * 1.02).all())


rng = np.random.default_rng(7)
for span, lo, hi in (("2019-2023", date(2019, 6, 1), date(2023, 12, 31)), ("2024-2026", date(2024, 1, 1), date(2027, 1, 1))):
    sup, res, base_s, base_r = defaultdict(list), defaultdict(list), [], []
    for i in range(LOOK, n - H):
        if not (lo <= d[i] <= hi) or v[i - LOOK + 1:i + 1].sum() <= 0:
            continue
        lv = levels(i)
        cands = [("POC", lv["poc"]), ("value area low", lv["val"]), ("value area high", lv["vah"])] + \
                [("HVN", x) for x in lv["hvn"]]
        for name, x in cands:
            gap = (c[i] / x - 1) * 100
            if 0 <= gap <= 2:
                sup[name].append(holds_below(i, x))
            if -2 <= gap < 0:
                res[name].append(holds_above(i, x))
        base_s.append(holds_below(i, c[i] / (1 + rng.uniform(0, 0.02))))
        base_r.append(holds_above(i, c[i] * (1 + rng.uniform(0, 0.02))))
    print(f"\n{span}: a level with no history held as support {np.mean(base_s) * 100:.0f}%, as resistance {np.mean(base_r) * 100:.0f}%")
    for name in ("POC", "value area low", "value area high", "HVN"):
        s, r = sup.get(name, []), res.get(name, [])
        print(f"   {name:16} support: {len(s):4} days, held {np.mean(s) * 100 if s else float('nan'):3.0f}% "
              f"(edge {np.mean(s) * 100 - np.mean(base_s) * 100 if s else float('nan'):+3.0f} pp) | "
              f"resistance: {len(r):4} days, held {np.mean(r) * 100 if r else float('nan'):3.0f}% "
              f"(edge {np.mean(r) * 100 - np.mean(base_r) * 100 if r else float('nan'):+3.0f} pp)")

i = n - 1
lv = levels(i)
print(f"\ntoday ({d[i]}, 18K {c[i] / 1e7:.2f}M), last {LOOK} trading days: POC {lv['poc'] / 1e7:.2f}M, value area "
      f"{lv['val'] / 1e7:.2f}-{lv['vah'] / 1e7:.2f}M, HVNs {[round(x / 1e7, 2) for x in lv['hvn']]}")
