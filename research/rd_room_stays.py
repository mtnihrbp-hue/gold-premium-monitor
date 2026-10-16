"""How long the room parks, and what each stay earned (SP-D, SP_D_HANDOFF.md section 42; the owner,
2026-10-16: "how long park").

rd_parking.py and rd_room_breaks.py: no single break is worth following, alone or as a member; the room
as built is what beat holding (+5% to +9% per two years at Daric's cost). Its own stays out of gold are
the measured answer to "how long", and they have not been listed.

Rules, fixed before the run (a report, no verdict):
- The room as built: analysis/room.py's eight members and weights, section 27's rule (out at 60% of the
  weight with a view, back at 30%), 10-day reviews from offset 0, the stock index's veto and turn;
  rd_trend_room.room(), as the paired tests ran it. Its first review on the first day every member has
  a view, to 2026-10-01 (the harness's last day).
- Each stay: from the review that moves 40% of the grams into the fund to the day they come back. Its
  length in trading days; 18K's move and the fund's over the stay; the gain of the stay for the whole
  holding, 0.40 x (the fund's growth / 18K's growth - 1), before costs.
- Reported: every stay; their count, median length and the share that gained; by year; the room's
  posture on the last day.

Run: python research/rd_room_stays.py
"""

import numpy as np

import rd_trend_room as T
from rd_rebuy import fi_log

R = T.R
c, d, n = R.c, R.d, R.n
level = np.exp(np.nan_to_num(fi_log - np.nanmin(fi_log)))


def main():
    first = next(i for i in range(n) if all(R.LEAN[m][i] != 0 or m in ("money flow",) for m in T.BASE)
                 and np.isfinite(fi_log[i]))
    first = max(first, next(i for i in range(n) if d[i].year >= 2016))
    idx = list(range(first, n))
    f = T.room(dict(T.BASE))(10, 0)(idx)
    held = np.array([f(i) for i in idx])
    stays, start = [], None
    for k, i in enumerate(idx):
        if held[k] and start is None:
            start = i
        elif not held[k] and start is not None:
            stays.append((start, i))
            start = None
    open_stay = start
    print(f"the room from {d[first]} to {d[-1]}: out of gold (40%) on {held.mean():.0%} of days, {len(stays)} completed stays")
    print(f"{'out':<12}{'back':<12}{'days':>5}{'18K':>9}{'fund':>8}{'gain (whole holding)':>22}")
    gains, lengths = [], []
    for a, b in stays:
        g18 = c[b] / c[a] - 1
        gf = level[b] / level[a] - 1
        gain = 0.40 * ((1 + gf) / (1 + g18) - 1) * 100
        gains.append(gain)
        lengths.append(b - a)
        print(f"{str(d[a]):<12}{str(d[b]):<12}{b - a:>5}{g18 * 100:>+8.1f}%{gf * 100:>+7.1f}%{gain:>+20.2f}%")
    if gains:
        print(f"\n{len(gains)} stays: median {np.median(lengths):.0f} trading days (from {min(lengths)} to {max(lengths)}); "
              f"gained in {np.mean([g > 0 for g in gains]):.0%}; mean gain {np.mean(gains):+.2f}%, "
              f"median {np.median(gains):+.2f}%, best {max(gains):+.2f}%, worst {min(gains):+.2f}%")
        years = sorted({d[a].year for a, _ in stays})
        for y in years:
            g = [gains[k] for k, (a, _) in enumerate(stays) if d[a].year == y]
            print(f"   {y}: {len(g)} stays, total {sum(g):+.2f}%")
    if open_stay is not None:
        print(f"\nON THE LAST DAY ({d[-1]}): out of gold since {d[open_stay]} ({n - 1 - open_stay} trading days)")
    else:
        last_back = stays[-1][1] if stays else None
        print(f"\nON THE LAST DAY ({d[-1]}): all in gold" + (f", back since {d[last_back]}" if last_back else ""))


if __name__ == "__main__":
    main()
