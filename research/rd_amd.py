"""AMD (accumulation, manipulation, distribution) and session liquidity, tested (SP-D, 2026-10-05).

The owner: "one thing missing is the session liquidity and AMD, or any other technique."

1. AMD in the gold funds' sessions (Ayyar and Tala, one-minute bars 2023-10 -> 2026-10): the first
   hour's range is the accumulation; a later break of one side (by 0.1%) the manipulation; a close
   beyond the OTHER side the distribution (AMD), a close beyond the SAME side a continuation. The
   benchmark: the same days with their minutes' returns shuffled (the day's moves kept, any
   structure inside the day destroyed), 20 shuffles. AMD is a pattern only if it is more frequent
   than in the shuffled days. Then: does the day's distribution foretell 18K's next 1 and 5 days?
2. Session liquidity: a run beyond yesterday's high (low) that closes back inside -- how often,
   against the shuffled days.
3. Our own market's session: the platforms' median price at each hour of the Tehran day against the
   same day's 21:00, on production's hourly readings (2026-08 -> 10): is one hour cheaper to buy?
"""
import json
import os
from collections import defaultdict
from datetime import date, datetime, timedelta

import numpy as np

from rd_rebuy import c, d

HERE = os.path.dirname(os.path.abspath(__file__))
gix = {x: i for i, x in enumerate(d)}
rng = np.random.default_rng(31)
TOL = 0.001


def classify(px, first_n):
    """'AMD up', 'AMD down', 'continuation up', 'continuation down', 'inside'."""
    hi, lo = px[:first_n].max(), px[:first_n].min()
    rest = px[first_n:]
    up = np.flatnonzero(rest > hi * (1 + TOL))
    dn = np.flatnonzero(rest < lo * (1 - TOL))
    close = px[-1]
    if not len(up) and not len(dn):
        return "inside"
    first_up = up[0] if len(up) else 10 ** 9
    first_dn = dn[0] if len(dn) else 10 ** 9
    if first_up < first_dn:        # the first break was up
        return "AMD down" if close < lo * (1 - TOL) else "continuation up" if close > hi * (1 + TOL) else "inside"
    return "AMD up" if close > hi * (1 + TOL) else "continuation down" if close < lo * (1 - TOL) else "inside"


for ins, name in (("34144395039913458", "Ayyar"), ("46700660505281786", "Tala")):
    F = json.load(open(os.path.join(HERE, "data", "tsetmc_intraday", f"{ins}.json"), encoding="utf-8"))
    real, shuf = defaultdict(int), defaultdict(float)
    sweeps, sweeps_s, prev = [0, 0], [0.0, 0.0], None
    nx = defaultdict(list)
    days = 0
    for key in sorted(F["days"]):
        bars = [b for b in (F["days"][key].get("bars") or []) if b[5] > 0]
        if len(bars) < 90:
            prev = None
            continue
        px = np.array([b[4] for b in bars], dtype=float)
        first_n = sum(1 for b in bars if (b[0] // 100) * 60 + b[0] % 100 < (bars[0][0] // 100) * 60 + bars[0][0] % 100 + 60)
        k = classify(px, first_n)
        real[k] += 1
        days += 1
        r = np.diff(np.log(px))
        for _ in range(20):
            sp = px[0] * np.exp(np.concatenate([[0], np.cumsum(rng.permutation(r))]))
            shuf[classify(sp, first_n)] += 1 / 20
        if prev is not None:
            hi_p, lo_p = prev
            sweeps[0] += px.max() > hi_p and px[-1] < hi_p
            sweeps[1] += px.min() < lo_p and px[-1] > lo_p
            for _ in range(5):
                sp = px[0] * np.exp(np.concatenate([[0], np.cumsum(rng.permutation(r))]))
                sweeps_s[0] += (sp.max() > hi_p and sp[-1] < hi_p) / 5
                sweeps_s[1] += (sp.min() < lo_p and sp[-1] > lo_p) / 5
        prev = (px.max(), px.min())
        dt = date(int(key[:4]), int(key[4:6]), int(key[6:]))
        i = gix.get(dt)
        if i is not None and i + 6 < len(c):
            nx[k].append(((c[i + 1] / c[i] - 1) * 100, (c[i + 6] / c[i + 1] - 1) * 100))
    print(f"\n{name}: {days} sessions")
    print("   day type             real    shuffled minutes   18K tomorrow   18K the 5 days after")
    for k in ("AMD up", "AMD down", "continuation up", "continuation down", "inside"):
        v = np.array(nx[k]) if nx[k] else np.zeros((0, 2))
        print(f"   {k:18} {real[k] / days * 100:5.1f}%   {shuf[k] / days * 100:5.1f}%            "
              f"{np.mean(v[:, 0]) if len(v) else np.nan:+6.2f}%       {np.mean(v[:, 1]) if len(v) else np.nan:+6.2f}%   ({len(v)})")
    print(f"   session liquidity: ran yesterday's high and closed back under it on {sweeps[0] / days * 100:.1f}% of days "
          f"(shuffled {sweeps_s[0] / days * 100:.1f}%); ran yesterday's low and closed back over it {sweeps[1] / days * 100:.1f}% "
          f"(shuffled {sweeps_s[1] / days * 100:.1f}%)")

# 3. the platforms' hour of the day
H = json.load(open(os.path.join(HERE, "data", "hourly.json")))
by_day = defaultdict(list)
for r in H:
    t = datetime.fromisoformat(r["ts"]) + timedelta(hours=3, minutes=30)
    p = [v for v in r["prices"].values() if v]
    if len(p) >= 5:
        by_day[t.date()].append((t.hour, float(np.median(p))))
rel = defaultdict(list)
for day, pts in by_day.items():
    end = [p for h, p in pts if h >= 20]
    if not end or len(pts) < 8:
        continue
    for h, p in pts:
        rel[h].append((p / end[-1] - 1) * 100)
print(f"\n3. THE PLATFORMS' DAY ({len(by_day)} days, 2026-08 -> 10): the median platform price at each hour against the "
      "same day's evening price")
print("   " + "  ".join(f"{h:02d}:00 {np.mean(rel[h]):+.2f}% ({len(rel[h])})" for h in sorted(rel)))
