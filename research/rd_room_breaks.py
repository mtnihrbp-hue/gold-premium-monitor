"""Trend breaks as members of the room (SP-D, SP_D_HANDOFF.md section 42; the owner, 2026-10-16).

rd_parking.py: alone, no break is worth following on a reader's record. Parking paid per episode, but the
whipsaws, the costs and the jumps missed took it back; the nearest was EMA20 under EMA50 for 40 days with
40% of the holding. The room trades only on a broad agreement, 40% at a time, so a break is tested where
it would serve: as one more member, by section 33's paired test against the production room.

Rules, fixed before the run (section 32's protocol, unchanged; rd_trend_room.py's harness):
- Candidates, each a lean at day i's close (+1 gold, -1 fixed income, 0 none):
    EMA cross         -1 when EMA20 is under EMA50, else +1
    EMA cross out     -1 when EMA20 is under EMA50, else 0 (it only votes to leave)
    18K 50-day        -1 when 18K is under its 50-day, else +1
    dollar 50-day     -1 when the dollar is under its 50-day, else +1
    both 50-day       -1 when both are under, +1 when both are over, else 0
- Test 1, alone: gold over fixed income in the next 20 trading days (log %) by lean, 2016-2020 and
  2021-2026.
- Test 2, in the room: the production room as built (analysis/room.py's eight members and weights), each
  candidate added at weight 1.0, paired against the room as built: 18 Afran windows from 2020 and 27
  index windows from 2018, offsets 0-9, Daric's 0.30% and Goldika's 2.37%.
- Acceptance (section 32): +0.5 points or more at the median over offsets, 60% of windows or more
  improved, the worst window not lower by more than 1 point, at both costs and in both window sets.

Run: python research/rd_room_breaks.py   (several minutes: every window, offset and variant)
"""

import numpy as np
import talib

import rd_trend_room as T
from rd_rebuy import usd

R = T.R
c, n = R.c, R.n
e20, e50 = talib.EMA(c, 20), talib.EMA(c, 50)
s50 = talib.SMA(c, 50)
u50 = talib.SMA(np.asarray(usd, dtype=float), 50)
known = np.isfinite(e50) & np.isfinite(s50)
below18 = known & (c < s50)
below_usd = np.isfinite(u50) & (np.asarray(usd) < u50)

CAND = {
    "EMA cross": np.where(~known, 0, np.where(e20 < e50, -1, 1)),
    "EMA cross out": np.where(~known, 0, np.where(e20 < e50, -1, 0)),
    "18K 50-day": np.where(~known, 0, np.where(below18, -1, 1)),
    "dollar 50-day": np.where(~np.isfinite(u50), 0, np.where(below_usd, -1, 1)),
    "both 50-day": np.where(below18 & below_usd, -1, np.where(known & ~below18 & np.isfinite(u50) & ~below_usd, 1, 0)),
}
for name, lean in CAND.items():
    R.LEAN[name] = lean.astype(int)
    R.MEMBERS.append(name)
    R.PROPOSED[name] = 0.0
T.CAND = CAND

PROD = dict(T.BASE)
T.VARIANTS = {"room as built": T.room(PROD)}
for name in CAND:
    T.VARIANTS[f"+ {name}"] = T.room(dict(PROD, **{name: 1.0}))

if __name__ == "__main__":
    print("production weights:", PROD)
    T.alone()
    T.in_room()
