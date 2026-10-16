"""Would a simpler room do as well? (SP-D, SP_D_HANDOFF.md section 36, the audit.)

The production room has eight members (analysis/room.py WEIGHTS). Section 31's leave-one-out found the
chartist and the dollar's 20 days add nothing, and rd_flow_saffron.py found money flow's measured gain
came from the saffron fund. This runs section 33's paired test -- rd_trend_room's production room ("veto +
turn", 10-day reviews), 18 Afran windows from 2020 and 27 index windows from 2018, offsets 0-9, Daric's
0.30% and Goldika's 2.37% -- with the production room as the base, against:
  - without money flow (seven members)
  - without money flow, the chartist and the dollar's 20 days (five members)
and reports each against holding too. Nothing else changes.
"""

import rd_trend_room as T

PROD = dict(T.BASE)
print("production weights:", PROD)
FIVE = {m: w for m, w in PROD.items() if m not in ("money flow", "chartist", "dollar 20d")}
T.VARIANTS = {"room as built": T.room(PROD),
              "7: no money flow": T.room(dict(T.NOF)),
              "5: no flow/chart/usd20": T.room(FIVE)}
T.in_room()
