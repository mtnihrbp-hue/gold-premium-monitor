"""src/analysis/room.py against the research room (rd_committee_2y.py and friends) on the same data."""
import json
import os
import sys
from datetime import date

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
import rd_committee_2y as R  # noqa: E402
import rd_committee_stocks  # noqa: E402,F401
from analysis import room  # noqa: E402
from caluclator.chartist import Chartist  # noqa: E402
from rd_rebuy import fi_log, flat, h, l, ons, usd  # noqa: E402

seed_ted = json.load(open(os.path.join(HERE, "..", "src", "seed", "tedpix.json")))
td = sorted(date.fromisoformat(k) for k in seed_ted)
ted = room.aligned(R.d, td, [seed_ted[k.isoformat()] for k in td])
fi = np.exp(fi_log)                                   # the research room's cost of money
ch = Chartist(h, l, R.c, usable=~flat)
first = next(i for i in range(R.n) if R.d[i] >= date(2018, 1, 1))
leans, stocks = room.member_leans(h, l, R.c, usd, ons, fi, ted, R.F_STAR, flat, chartist=ch, from_index=first)
for m in room.WEIGHTS:
    a, b = np.asarray(leans[m])[first:], np.asarray(R.LEAN[m])[first:]
    print(f"   {m:15} the same lean on {np.mean(a == b) * 100:6.2f}% of days since 2018")
a, b = np.asarray(stocks)[first:], np.asarray(R.LEAN["stocks 20d"])[first:]
print(f"   {'stocks 20d':15} the same lean on {np.mean(a == b) * 100:6.2f}% of days since 2018")

# the posture over the last two years, against the research room (no money flow, the stock return, every 10)
from rd_room_reentry_sense import variant  # noqa: E402
i0, i1 = next(i for i in range(R.n) if R.d[i] >= R.START), max(i for i in range(R.n) if R.d[i] <= R.END)
idx = list(range(i0, i1 + 1))
f = variant("veto + turn")(10, 0)(idx)
research = [f(i) for i in idx]
prod = [d_["posture"] == room.SWING_OUT for d_ in room.replay(leans, stocks, i0, i1)]
print(f"posture, the last two years: the same on {np.mean(np.array(research) == np.array(prod)) * 100:.2f}% of {len(idx)} days")
