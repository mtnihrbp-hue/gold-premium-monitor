"""Brave trader, hourly evidence: do platform prices lag fair value, and does a platform's
discount return to its usual level? (SP-D, 2026-10-04)

Data: production's non-user readings 2026-08-04 -> 2026-10-04 (610 readings, 62 days,
median 9 a day), exported to research/data/hourly.json (not committed: production data).
For a venue v at reading t: premium_v(t) = price_v / fair - 1.

1. CATCH-UP: when fair value moves by at least 0.5% between two readings, how much of the
   move does the venue's price make over the next 1, 3 and 9 readings?
2. REVERSION: when the venue's premium sits at least 0.7 pp from its own trailing 3-day
   mean, how does the venue's price move over the next ~day (9 readings), and does the
   premium come back?
"""
import json
import os
import sys
from datetime import datetime

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
rows = json.load(open(os.path.join(HERE, "data", "hourly.json")))
rows = [r for r in rows if r.get("fair")]
ts = [datetime.fromisoformat(r["ts"]) for r in rows]
fair = np.array([r["fair"] for r in rows])

for venue in ("Daric", "Goldika", "Ayyareh", "Milli"):
    price = np.array([r["prices"].get(venue, np.nan) for r in rows])
    ok = ~np.isnan(price)
    prem = price / fair - 1
    print(f"\n==== {venue}: {ok.sum()} readings")

    # 1. catch-up after a fair-value move
    for thr in (0.5, 1.0):
        out = {1: [], 3: [], 9: []}
        for t in range(1, len(rows) - 9):
            if not (ok[t - 1] and ok[t]):
                continue
            dfair = (fair[t] / fair[t - 1] - 1) * 100
            dprice = (price[t] / price[t - 1] - 1) * 100
            if abs(dfair) < thr:
                continue
            lag = dfair - dprice                      # the part of the fair move not yet made
            for k in out:
                if ok[t + k]:
                    out[k].append((np.sign(dfair), (price[t + k] / price[t] - 1) * 100, lag))
        n = len(out[1])
        if not n:
            continue
        desc = []
        for k, v in out.items():
            arr = np.array(v)
            follow = np.mean(arr[:, 0] * arr[:, 1])  # positive = price kept moving the fair move's way
            desc.append(f"{k} readings later {follow:+.2f}%")
        lag = np.mean([abs(x[2]) for x in out[1]])
        print(f"  fair moved >= {thr}% ({n} times; mean part not yet made {lag:.2f} pp): venue then moved the same way: "
              + ", ".join(desc))

    # 2. reversion of the premium to its trailing 3-day mean
    for thr in (0.7, 1.0):
        res = []
        for t in range(30, len(rows) - 9):
            if not ok[t] or not ok[t + 9]:
                continue
            window = [prem[j] for j in range(t - 30, t) if ok[j] and (ts[t] - ts[j]).days <= 3]
            if len(window) < 10:
                continue
            dev = (prem[t] - np.mean(window)) * 100
            if abs(dev) < thr:
                continue
            res.append((np.sign(dev), (price[t + 9] / price[t] - 1) * 100,
                        (prem[t + 9] - np.mean(window)) * 100 / dev))
        if res:
            arr = np.array(res)
            cheap = arr[arr[:, 0] < 0]
            rich = arr[arr[:, 0] > 0]
            def line(a, label):
                if not len(a):
                    return f"{label}: none"
                return (f"{label} {len(a)}: price next ~day {np.mean(a[:, 1]):+.2f}% (median {np.median(a[:, 1]):+.2f}%), "
                        f"premium gap left {np.median(a[:, 2]) * 100:.0f}%")
            print(f"  premium >= {thr} pp off its 3-day mean -> " + line(cheap, "more discounted than usual") + " | "
                  + line(rich, "less discounted than usual"))
