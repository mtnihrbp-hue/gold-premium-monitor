"""How fast the platforms follow fair value (SP-D, SP_D_HANDOFF.md section 38.3, the discount laboratory's first
measurement; on research/data/hourly.json, 2026-08-04 to 10-04, before the full record returns on 11-01).

Rules, fixed before the run:
- Fair value: world gold x the dollar x 0.75 / 31.1035 as stored (`fair`); the platforms: the mean of the
  three cheapest prices (the reader's basis).
- A fair jump: fair value up (or down) by FAIR_JUMP (1%) or more between two consecutive readings at most 3 hours
  apart; jumps closer than 12 hours to the previous one are not counted again (episodes).
- Follow-through: the platforms' move from the reading before the jump to the first reading at least h hours
  after it (h = 1, 3, 6, 24), as a share of fair's own move over the same span; and the discount (basis against
  fair) at the jump and after.
- Control: the same measures from every reading, so a drift in both does not pass for following.
"""
import json
import os
import sys
from datetime import datetime, timedelta

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
FAIR_JUMP = 0.01


def load():
    rows = json.load(open(os.path.join(HERE, "data", "hourly.json"), encoding="utf-8"))
    pts = []
    for r in rows:
        p = sorted(v for v in r["prices"].values() if v)
        if len(p) >= 3 and r.get("fair"):
            pts.append((datetime.fromisoformat(r["ts"]), float(r["fair"]), float(np.mean(p[:3]))))
    return sorted(pts)


def after(pts, i, hours):
    t = pts[i][0] + timedelta(hours=hours)
    for j in range(i + 1, len(pts)):
        if pts[j][0] >= t:
            return j if pts[j][0] - t <= timedelta(hours=12) else None
    return None


def main():
    pts = load()
    print(f"{len(pts)} readings {pts[0][0]:%Y-%m-%d} .. {pts[-1][0]:%Y-%m-%d}")
    jumps, last = [], None
    for i in range(1, len(pts)):
        gap = pts[i][0] - pts[i - 1][0]
        move = pts[i][1] / pts[i - 1][1] - 1
        if gap <= timedelta(hours=3) and abs(move) >= FAIR_JUMP and (last is None or pts[i][0] - pts[last][0] >= timedelta(hours=12)):
            jumps.append(i)
            last = i
    print(f"fair jumps of {FAIR_JUMP:.0%}+: {len(jumps)} (up {sum(pts[i][1] > pts[i - 1][1] for i in jumps)}, "
          f"down {sum(pts[i][1] < pts[i - 1][1] for i in jumps)})")
    for h in (1, 3, 6, 24):
        shares, disc_at, disc_after = [], [], []
        for i in jumps:
            j = after(pts, i, h)
            if j is None:
                continue
            fair_move = pts[j][1] / pts[i - 1][1] - 1
            plat_move = pts[j][2] / pts[i - 1][2] - 1
            if abs(fair_move) >= 0.005:
                shares.append(plat_move / fair_move)
            disc_at.append((pts[i][2] / pts[i][1] - 1) * 100)
            disc_after.append((pts[j][2] / pts[j][1] - 1) * 100)
        ctrl = []
        for i in range(1, len(pts)):
            j = after(pts, i, h)
            if j is None:
                continue
            fm = pts[j][1] / pts[i - 1][1] - 1
            if abs(fm) >= 0.005:
                ctrl.append((pts[j][2] / pts[i - 1][2] - 1) / fm)
        if shares:
            print(f"  +{h:>2}h: jumps n={len(shares):>2}: platforms made up a median {np.median(shares):.0%} of fair's move "
                  f"(control {np.median(ctrl):.0%}, n={len(ctrl)}); discount at the jump {np.median(disc_at):+.2f}%, "
                  f"{h}h later {np.median(disc_after):+.2f}%")


if __name__ == "__main__":
    main()
