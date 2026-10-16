"""The money-flow member without the saffron fund (SP-D, SP_D_HANDOFF.md section 36, the audit).

Section 33 measured the member on 19 "gold funds" that include سافرون (insCode 51200575796028449), a
saffron fund (section 35.7). This reruns section 33's own test -- rd_trend_room's production room ("veto +
turn", 10-day reviews), paired window by window against the room without money flow: 18 Afran windows
from 2020 and 27 index windows from 2018, offsets 0-9, Daric's 0.30% and Goldika's 2.37% -- with the
member built twice, the same way (the 20-day mean of buyer power, z-scored, +1 strong), once on the 19
funds as built and once on the 18 without saffron. Nothing else changes.
"""

import json
import os
from bisect import bisect_right
from collections import defaultdict
from datetime import date

import numpy as np

import rd_trend_room as T

R = T.R
HERE = os.path.dirname(os.path.abspath(__file__))
SAFFRON = "51200575796028449"


def flow_without(codes_out):
    F = json.load(open(os.path.join(HERE, "data", "tsetmc_gold_funds.json"), encoding="utf-8"))
    agg = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0])
    for code, fund in F.items():
        if code in codes_out:
            continue
        for f in fund["flows"]:
            s = str(f["recDate"])
            a = agg[date(int(s[:4]), int(s[4:6]), int(s[6:]))]
            for k, key in enumerate(("buy_I_Value", "buy_I_Count", "sell_I_Value", "sell_I_Count")):
                a[k] += float(f.get(key) or 0)
    fdays = sorted(k for k, a in agg.items() if a[1] and a[3] and a[2])
    power = np.array([(agg[k][0] / agg[k][1]) / (agg[k][2] / agg[k][3]) for k in fdays])
    power20 = np.array([np.mean(power[max(0, j - 19):j + 1]) for j in range(len(power))])
    return np.array([power20[bisect_right(fdays, x) - 1]
                     if bisect_right(fdays, x) and (x - fdays[bisect_right(fdays, x) - 1]).days < 7 else np.nan
                     for x in R.d])


with_saffron = flow_without(set())
assert np.allclose(np.nan_to_num(with_saffron), np.nan_to_num(R.flow)), "the rebuild must match the research's flow"
R.LEAN["money flow (18 funds)"] = R.lean_from_z(R.zscore(flow_without({SAFFRON})), +1)
lean19, lean18 = R.LEAN["money flow"], R.LEAN["money flow (18 funds)"]
both = (lean19 != 0) | (lean18 != 0)
print(f"days the two votes differ: {np.sum(lean19 != lean18)} of {np.sum(both)} days either votes "
      f"({np.mean(lean19[both] != lean18[both]) * 100:.1f}%)")

T.VARIANTS = {"room as built": T.room(dict(T.NOF)),
              "+ flow, 19 funds": T.room(dict(T.NOF, **{"money flow": 0.5})),
              "+ flow, 18 funds": T.room(dict(T.NOF, **{"money flow (18 funds)": 0.5}))}
T.in_room()
