"""The room's headline with the trade a day or two after the decision (SP-D, SP_D_HANDOFF.md section 53; the
external audit's B4: "the room's headline fills at the same close that produced the signal ... Re-run the
headline at lag 1 and lag 2").

The harness (rd_committee_2y.evaluate) decides on day i's close and trades at that close: "lag 0, the owner's
contract". Production reads completed tgju candles and trades at the next run's platform quote, a day later
at the least. Same-close fills flatter the members that fire on the close itself.

Rules, fixed before the run:
- The room as built (rd_trend_room's room(BASE): analysis/room.py's eight members and weights, 10-day reviews,
  the stock index's veto and turn), on the research data of 2026-10-18 (the 19 gold funds, section 49).
- Lag L = 0, 1, 2: the swing's position on day i is the one the room decided at the close of day i - L; the
  trade, when there is one, is at day i's close. The room's own state runs in order, unchanged; only the
  trade moves. Before L days have passed, the swing is in gold.
- Windows, offsets and costs as rd_trend_room.in_room: 18 Afran windows from 2020 and 27 index windows from
  2018, two years each, offsets 0-9, Daric's 0.30% and Goldika's 2.37% round trip.
- Prices: tgju's close, as the harness. Platform-side prices have no daily history to 2018; tgju's close
  sits about 0.19% above the platforms (direction.TGJU_OFFSET_PCT), and the costs above carry the spread.
- Reported per lag and set: the median over holding (lowest to highest over offsets), the windows ahead,
  the worst window.
- Verdict, decided now: the published figure (+4.1% to +7.2%, Afran, Daric) is restated at lag 1 as the
  room's figure. The room "still beats holding" if at lag 2 the lowest median over offsets is above zero
  in all four sets; otherwise it does not on this record.

Run: python research/rd_room_lag.py   (several minutes)
"""

import numpy as np

import rd_trend_room as T


def lagged(room_fn, lag):
    """room_fn(every, offset)(idx) -> out_on(i); the same, with the position taken from `lag` days earlier."""
    if lag == 0:
        return room_fn

    def at(every, offset):
        def factory(idx):
            inner = room_fn(every, offset)(idx)
            seen = []

            def out_on(i):
                seen.append(bool(inner(i)))          # the room's state runs in order, every day
                return seen[-1 - lag] if len(seen) > lag else False
            return out_on
        return factory
    return at


def main():
    base = T.room(dict(T.BASE))
    T.VARIANTS = {f"lag {lag}": lagged(base, lag) for lag in (0, 1, 2)}
    R = T.R
    R.AFRAN_LEVEL = R.af_level.copy()
    rows = {}
    for cost in (0.30, 2.37):
        R.GOLD_HALF = cost / 200
        for label, first, last, park in (("Afran windows from 2020", T.date(2020, 6, 1), T.date(2024, 10, 5), "afran"),
                                         ("index windows from 2018", T.date(2018, 1, 1), T.date(2024, 10, 5), "index")):
            nw, t = T.windows(first, last, park)
            print(f"\nround trip {cost:.2f}%, {label} ({nw}), against holding")
            for v in T.VARIANTS:
                arr = {o: np.array(t[f"{v}|{o}"]) for o in range(10)}
                meds = [np.median(arr[o]) * 100 for o in range(10)]
                ahead = [np.mean(arr[o] > 0.0005) * 100 for o in range(10)]
                worst = min(arr[o].min() for o in range(10)) * 100
                rows[(cost, label, v)] = min(meds)
                print(f"   {v:6} median {min(meds):+5.1f} to {max(meds):+5.1f}%   ahead {min(ahead):3.0f}-{max(ahead):3.0f}%"
                      f"   worst {worst:+6.1f}%")
    still = all(rows[(cost, label, "lag 2")] > 0 for cost in (0.30, 2.37)
                for label in ("Afran windows from 2020", "index windows from 2018"))
    print("\nVERDICT: at lag 2 the room " + ("still beats holding in all four sets" if still
                                             else "does not beat holding in all four sets on this record"))


if __name__ == "__main__":
    main()
