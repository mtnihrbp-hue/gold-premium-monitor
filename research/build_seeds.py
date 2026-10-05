"""Seed histories for the room's members that production cannot fetch from GitHub's runner (SP-D, 2026-10-05).

TEDPIX (TSETMC, from Iran) and the cost of money -- the fixed-income index (the median fund's daily total
return, rd_rebuy.py) before Afran exists, Afran's price after (accumulating: no payouts, its price is its
total return) -- written to src/seed/*.json. From 2026-10-04 production appends its own daily readings
from tablokhani (TEDPIX, Afran's close), which GitHub's runner reaches."""
import json
import os
from bisect import bisect_right
from datetime import date

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "src", "seed")
ted = sorted(json.load(open(os.path.join(HERE, "data", "tedpix.json"))), key=lambda r: r["dEven"])
tedpix = {f"{r['dEven'] // 10000:04d}-{(r['dEven'] // 100) % 100:02d}-{r['dEven'] % 100:02d}": round(r["xNivInuClMresIbs"], 2)
          for r in ted}
json.dump(tedpix, open(os.path.join(OUT, "tedpix.json"), "w"), separators=(",", ":"))

from rd_rebuy import FI, d, fi_log  # noqa: E402
af = next(f for f in FI.values() if f["symbol"] == "افران")
ap = sorted((date(int(x["date"][:4]), int(x["date"][4:6]), int(x["date"][6:])), float(x["close"])) for x in af["prices"]
            if x["close"] > 0)
first_af = ap[0][0]
level = {}
for x, v in zip(d, fi_log):
    if np.isfinite(v) and x < first_af:
        level[x] = float(np.exp(v))
scale = level[max(level)] / ap[0][1]
for x, v in ap:
    level[x] = v * scale
fi = {k.isoformat(): round(v, 6) for k, v in sorted(level.items())}
json.dump({"chained_at": first_af.isoformat(), "afran_scale": scale, "level": fi}, open(os.path.join(OUT, "fixed_income.json"), "w"),
          separators=(",", ":"))
print(f"tedpix: {len(tedpix)} days {min(tedpix)} -> {max(tedpix)};  cost of money: {len(fi)} days {min(fi)} -> {max(fi)}, "
      f"Afran from {first_af}")

# does the real-dollar member read the same on Afran as on the index it was tested with?
import rd_committee_2y as R  # noqa: E402
ks = sorted(level)
lv = np.array([np.log(level[ks[bisect_right(ks, x) - 1]]) if bisect_right(ks, x) else np.nan for x in d])
from rd_rebuy import against_own, usd  # noqa: E402
alt = R.lean_from_z(R.zscore(against_own(np.log(usd) - lv, 500)), -1)
orig = R.LEAN["real dollar"]
sel = np.array([x >= date(2022, 1, 1) for x in d]) & ((alt != 0) | (orig != 0))
print(f"real dollar on Afran against on the index: the same lean on {np.mean(alt[sel] == orig[sel]) * 100:.0f}% of days since 2022")
