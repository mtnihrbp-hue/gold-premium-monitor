"""Money rotating between the Tehran stock market and gold (SP-D, 2026-10-05).

TEDPIX daily from TSETMC (Index/GetIndexB2History/32097828799138957), fetched from Iran. Does the
stock index's last 20 / 60 days, or its move against 18K's (rotation), foresee 18K's next 20 days
and gold over fixed income over 60? After 18K's own last 5 and 20 days; circular-shift luck."""
import json
import os
from bisect import bisect_right
from datetime import date

import numpy as np
import requests
from scipy.stats import rankdata

from rd_rebuy import X60, c, d, n

HERE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(HERE, "data", "tedpix.json")
if not os.path.exists(P):
    s = requests.Session()
    s.trust_env = False
    j = s.get("https://cdn.tsetmc.com/api/Index/GetIndexB2History/32097828799138957", timeout=60,
              headers={"User-Agent": "Mozilla/5.0"}).json()
    json.dump(j["indexB2"], open(P, "w"))
rows = sorted(json.load(open(P)), key=lambda r: r["dEven"])
td = [date(r["dEven"] // 10000, (r["dEven"] // 100) % 100, r["dEven"] % 100) for r in rows]
tv = np.array([r["xNivInuClMresIbs"] for r in rows], dtype=float)
idx = np.array([tv[bisect_right(td, x) - 1] if bisect_right(td, x) else np.nan for x in d])


def back(a, k):
    out = np.full(n, np.nan)
    out[k:] = (a[k:] / a[:-k] - 1) * 100
    return out


def fwd(h):
    out = np.full(n, np.nan)
    out[:n - 1 - h] = (c[1 + h:] / c[1:n - h] - 1) * 100
    return out


S = {"TEDPIX 20 days": back(idx, 20), "TEDPIX 60 days": back(idx, 60),
     "rotation 20 days (TEDPIX - 18K)": back(idx, 20) - back(c, 20), "rotation 60 days": back(idx, 60) - back(c, 60)}
Y = {"18K 20d": fwd(20), "gold-FI 60d": X60}
CT = [back(c, 5), back(c, 20)]
rng = np.random.default_rng(23)
for label, lo, hi in (("2014-2019", date(2014, 1, 1), date(2019, 12, 31)), ("2020-2026", date(2020, 1, 1), date(2026, 12, 31))):
    sel = np.array([lo <= x <= hi for x in d])
    for name, s in S.items():
        cells = []
        for t, y in Y.items():
            ok = sel & np.isfinite(s) & np.isfinite(y) & np.isfinite(CT[0]) & np.isfinite(CT[1])
            m = ok.sum()
            X = np.column_stack([np.ones(m)] + [rankdata(x[ok]) / m for x in CT])
            res = lambda v: v - X @ np.linalg.lstsq(X, v, rcond=None)[0]
            a, b = res(rankdata(s[ok]) / m), res(rankdata(y[ok]) / m)
            v = np.corrcoef(a, b)[0, 1]
            null = [np.corrcoef(np.roll(a, rng.integers(60, m - 60)), b)[0, 1] for _ in range(300)]
            cells.append(f"{t} {v:+.2f} (luck {np.mean(np.abs(null) >= abs(v)) * 100:3.0f}%)")
        print(f"   {label} {name:33} " + "   ".join(cells))

# is it the dollar or world gold in disguise? the same, after the dollar's and world gold's last 5 and 20 days too
from rd_rebuy import ons, usd  # noqa: E402
CT2 = CT + [back(usd, 5), back(usd, 20), back(ons, 5), back(ons, 20)]
print("\n   after 18K's, the dollar's and world gold's own last 5 and 20 days:")
for label, lo, hi in (("2014-2019", date(2014, 1, 1), date(2019, 12, 31)), ("2020-2026", date(2020, 1, 1), date(2026, 12, 31)),
                      ("2020-2022", date(2020, 1, 1), date(2022, 12, 31)), ("2023-2026", date(2023, 1, 1), date(2026, 12, 31))):
    sel = np.array([lo <= x <= hi for x in d])
    for name in ("TEDPIX 20 days", "TEDPIX 60 days"):
        s = S[name]
        cells = []
        for t, y in Y.items():
            ok = sel & np.isfinite(s) & np.isfinite(y)
            for x in CT2:
                ok &= np.isfinite(x)
            m = ok.sum()
            X = np.column_stack([np.ones(m)] + [rankdata(x[ok]) / m for x in CT2])
            res = lambda v: v - X @ np.linalg.lstsq(X, v, rcond=None)[0]
            a, b = res(rankdata(s[ok]) / m), res(rankdata(y[ok]) / m)
            v = np.corrcoef(a, b)[0, 1]
            null = [np.corrcoef(np.roll(a, rng.integers(60, m - 60)), b)[0, 1] for _ in range(300)]
            cells.append(f"{t} {v:+.2f} (luck {np.mean(np.abs(null) >= abs(v)) * 100:3.0f}%)")
        print(f"   {label} {name:33} " + "   ".join(cells))
