"""Does 18K follow a move in its fair value (world gold x the dollar) a day later?
(SP-D, 2026-10-04; the 12-year counterpart of rd_swing_hourly.py's catch-up test)

fair(t) = world gold (USD/oz, tgju 'ons', last close on or before the Tehran day) x the
dollar (tgju, rial) x 0.75 / 31.1035. gap(t) = fair's move on day t minus 18K's move on
day t. If 18K lags, a large gap is followed by 18K moving the same way on day t+1.
In-sample 2014-2023, holdout 2024-2026.
"""
import json
import os
from bisect import bisect_right
from datetime import date

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(HERE, "data", "tgju_history.json")))
g = [(date.fromisoformat(r["date"]), float(r["close"])) for r in D["geram18"]]
u = [(date.fromisoformat(r["date"]), float(r["close"])) for r in D["price_dollar_rl"]]
x = [(date.fromisoformat(r["date"]), float(r["close"])) for r in D["ons"]]
ud, uc = [a for a, _ in u], [b for _, b in u]
xd, xc = [a for a, _ in x], [b for _, b in x]


def last(dates, closes, day):
    k = bisect_right(dates, day) - 1
    return closes[k] if k >= 0 else None


days = [a for a, _ in g]
gold = np.array([b for _, b in g])
fair = np.array([last(xd, xc, a) * last(ud, uc, a) * 0.75 / 31.1035 if last(xd, xc, a) and last(ud, uc, a) else np.nan
                 for a in days])
rg = np.full(len(g), np.nan); rf = np.full(len(g), np.nan)
rg[1:] = (gold[1:] / gold[:-1] - 1) * 100
rf[1:] = (fair[1:] / fair[:-1] - 1) * 100
gap = rf - rg
nxt = np.full(len(g), np.nan); nxt[:-1] = rg[1:]
nxt3 = np.full(len(g), np.nan); nxt3[:-3] = (gold[3:] / gold[:-3] - 1) * 100

for name, lo, hi in (("2014-2023", date(2014, 1, 1), date(2023, 12, 31)), ("2024-2026", date(2024, 1, 1), date(2027, 1, 1))):
    sel = [i for i in range(1, len(g) - 3) if lo <= days[i] <= hi and not np.isnan(gap[i])]
    base1, base3 = np.mean(nxt[sel]), np.mean(nxt3[sel])
    print(f"\n{name}: {len(sel)} days; 18K next day {base1:+.2f}% / next 3 days {base3:+.2f}% on average")
    for thr in (1.0, 2.0, 3.0):
        up = [i for i in sel if gap[i] >= thr]
        dn = [i for i in sel if gap[i] <= -thr]
        def s(idx):
            if not idx:
                return "none"
            return (f"{len(idx):4} days: next day {np.mean(nxt[idx]):+.2f}% (higher {np.mean(nxt[idx] > 0) * 100:.0f}%), "
                    f"next 3 days {np.mean(nxt3[idx]):+.2f}%")
        print(f"  fair ran ahead of 18K by >= {thr}%: {s(up)}")
        print(f"  fair fell behind 18K by >= {thr}%: {s(dn)}")
    corr = np.corrcoef(gap[sel], nxt[sel])[0, 1]
    print(f"  correlation of today's gap with tomorrow's 18K move: {corr:+.2f}")
