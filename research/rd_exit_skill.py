"""Each candidate member as the room uses it: when it says fixed income, how often does fixed income
win over the next 20 days, against the base rate? (SP-D, 2026-10-05)"""
from datetime import date

import numpy as np

import rd_committee_2y as R
import rd_committee_stocks  # noqa: F401  (adds 'stocks 20d' to R.LEAN)
import rd_vp_member  # noqa: F401  (adds 'volume profile')
from rd_rebuy import X20, X60

SPANS = (("2018-2021", date(2018, 1, 1), date(2021, 12, 31)), ("2022-2026", date(2022, 1, 1), date(2026, 12, 31)))
print("\nwhen the member says FIXED INCOME: share of days fixed income then beat gold (20 days | 60 days), and days")
for label, lo, hi in SPANS:
    sel = np.array([lo <= x <= hi for x in R.d]) & np.isfinite(X20) & np.isfinite(X60)
    print(f"   {label}: base rate (any day) {np.mean(X20[sel] < 0) * 100:.0f}% | {np.mean(X60[sel] < 0) * 100:.0f}%")
    for m in R.MEMBERS:
        f = sel & (R.LEAN[m] == -1)
        if f.sum() < 20:
            continue
        print(f"      {m:16} {np.mean(X20[f] < 0) * 100:4.0f}% | {np.mean(X60[f] < 0) * 100:4.0f}%   ({f.sum()} days)")
