"""Sideways channels: park in fixed income, or trade the box? (SP-D, SP_D_HANDOFF.md section 44; the owner,
2026-10-17: "the backtest has repeatedly confirmed the hold, but the problem as i have raised several times, is
the times the gold enter a sideway channel. and now the only way you are relying upon is the EMA method ...
how we can fix this.")

In a flat market gold earns nothing while the fixed-income fund pays about 2% a month in rial. The owner's
room of 2026-10-05: "if sideways, ... sell some gold into fixed income and keep the rest, and keep a sharp
eye to rebuy the sold gold back." 42.1 tested trend breaks, not boxes; this tests the box itself.

Rules, fixed before the run:
- Data: research/data/tgju_history.json (tgju's daily 18K and dollar, to 2026-10-02); the fixed-income fund's
  level (src/seed/fixed_income.json, from 2015-03-15).
- Detectors, each known at day i's close from closes up to i:
    BOX        the pattern reader's running range (caluclator/patterns.ranges on the last 250 closes): 8 closes
               or more within 6% of each other, entered after a move of 8%; on while it runs
    ROOM RULE  the room's market-state rule (room.efficiency_sideways and no new 60-day high in 20 days)
    BOTH BOXES 18K's box and the dollar's box at once
- Policies, each with 40% and with 100% of the holding:
    PARK THE BOX   into the fund when the detector turns on; back to gold when it turns off (after 3 days
                   at least)
    TRADE THE BOX  (BOX only) inside a running box: into the fund when the close is in the box's upper third;
                   back to gold when it is in the lower third, or when it leaves the box upward (a close
                   0.5% over its top); if it leaves downward, stay in the fund until 18K closes back over its
                   EMA20
- The reader's record: starts all in gold; one move at a time; each move costs half a round trip, Daric's
  0.30% and Goldika's 2.37%; two-year windows starting every 20 trading days from 2015-03-15; the end value
  against holding 18K; by start era (2015-2019, 2020-2024): the median, the share of windows ahead, the
  worst.
- Context, reported: the share of days 18K spends in a box; 18K's and the fund's mean monthly return
  while it is in one, and outside.
- Verdict, decided now (rd_parking.py's): a policy is WORTH FOLLOWING when, at both costs, its median over
  windows is at least +0.5 points above holding in both start eras, it is ahead in at least 60% of all
  windows, and its worst window is no lower than -5%. Otherwise NOT WORTH FOLLOWING; the closest is named.

Run: python research/rd_sideways_box.py
"""

import json
import os
import sys
from bisect import bisect_right
from datetime import date

import numpy as np
import talib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
from analysis.room import efficiency_sideways  # noqa: E402
from caluclator import patterns  # noqa: E402

WINDOW, STEP = 500, 20
COSTS = (("Daric 0.30%", 0.0030), ("Goldika 2.37%", 0.0237))
START_ERAS = (("2015-2019", date(2015, 3, 15), date(2019, 12, 31)), ("2020-2024", date(2020, 1, 1), date(2024, 12, 31)))
LOOKBACK = 250


def load():
    raw = json.load(open(os.path.join(HERE, "data", "tgju_history.json"), encoding="utf-8"))
    g = {date.fromisoformat(r["date"]): r for r in raw["geram18"] if r["close"] > 0}
    u = {date.fromisoformat(r["date"]): float(r["close"]) for r in raw["price_dollar_rl"] if r["close"] > 0}
    days = sorted(g)
    udays = sorted(u)
    close = np.array([float(g[d]["close"]) for d in days])
    usd = np.array([u[udays[max(0, bisect_right(udays, d) - 1)]] for d in days])
    fi = json.load(open(os.path.join(HERE, "..", "src", "seed", "fixed_income.json"), encoding="utf-8"))["level"]
    fdays = sorted(date.fromisoformat(k) for k in fi)
    level = np.array([fi[fdays[bisect_right(fdays, d) - 1].isoformat()] if bisect_right(fdays, d) else np.nan
                      for d in days], dtype=float)
    return days, close, usd, level


def running_box(c, i):
    """(low, high) of the box running on day i, or None (closes up to i only)."""
    lo_i = max(0, i - LOOKBACK)
    rngs = patterns.ranges(c[lo_i:i + 1])
    if rngs and rngs[-1][1] == i - lo_i:
        s, e, lo, hi, _ = rngs[-1]
        return float(lo), float(hi)
    return None


def main():
    days, close, usd, level = load()
    n = len(days)
    usable = np.isfinite(level)
    box18 = [running_box(close, i) for i in range(n)]
    boxusd = [running_box(usd, i) for i in range(n)]
    ema20 = talib.EMA(close, 20)
    high60 = np.array([i >= 60 and close[i] >= close[i - 59:i + 1].max() for i in range(n)])
    new_high_20 = np.array([i >= 80 and high60[i - 19:i + 1].any() for i in range(n)])
    room_rule = efficiency_sideways(close, np.zeros(n)) & ~new_high_20
    on = {"BOX": np.array([b is not None for b in box18]),
          "ROOM RULE": room_rule,
          "BOTH BOXES": np.array([box18[i] is not None and boxusd[i] is not None for i in range(n)])}

    # context: time in a box, and returns in and out of one (monthly, 21 trading days)
    ix = [i for i in range(n - 21) if usable[i] and usable[i + 21]]
    for name in on:
        inside = [i for i in ix if on[name][i]]
        outside = [i for i in ix if not on[name][i]]
        g_in = np.mean([close[i + 21] / close[i] - 1 for i in inside]) * 100 if inside else np.nan
        f_in = np.mean([level[i + 21] / level[i] - 1 for i in inside]) * 100 if inside else np.nan
        g_out = np.mean([close[i + 21] / close[i] - 1 for i in outside]) * 100 if outside else np.nan
        print(f"{name:<11} on {np.mean(on[name][[i for i in range(n) if usable[i]]]):.0%} of days; the next month while "
              f"on: 18K {g_in:+.2f}%, the fund {f_in:+.2f}% | while off: 18K {g_out:+.2f}%")

    def trade_box_targets():
        """For TRADE THE BOX: the wanted state (True = parked) per day, from the running box."""
        want, parked, broke_down = np.zeros(n, dtype=bool), False, False
        for i in range(n):
            b = box18[i]
            if broke_down:
                if np.isfinite(ema20[i]) and close[i] > ema20[i]:
                    broke_down, parked = False, False
            elif b is not None:
                lo, hi = b
                third = (hi - lo) / 3
                if close[i] >= hi - third:
                    parked = True
                elif close[i] <= lo + third:
                    parked = False
            elif parked:
                prev = box18[i - 1] if i else None
                if prev is not None and close[i] >= prev[1] * 1.005:
                    parked = False                 # left upward: back to gold
                elif prev is not None and close[i] < prev[0]:
                    broke_down = True              # left downward: stay out until over the EMA20
                else:
                    parked = False
            want[i] = parked or broke_down
        return want

    policies = {}
    for name, flag in on.items():
        want, parked_since = np.zeros(n, dtype=bool), None
        for i in range(n):
            if flag[i] and parked_since is None:
                parked_since = i
            elif parked_since is not None and not flag[i] and i - parked_since >= 3:
                parked_since = None
            want[i] = parked_since is not None
        policies[f"PARK THE BOX ({name})"] = want
    policies["TRADE THE BOX (BOX)"] = trade_box_targets()

    print("\nTHE READER'S RECORD: two-year windows against holding 18K (median 2015-2019 | 2020-2024, ahead, worst)")
    best, verdicts = None, {}
    first_usable = int(np.argmax(usable))
    starts = [s for s in range(first_usable, n - WINDOW) if (s - first_usable) % STEP == 0]
    for pname, want in policies.items():
        for share in (0.4, 1.0):
            ok_all, line, score = True, [], []
            for cost_label, rt in COSTS:
                half = rt / 2
                res = {e: [] for e, _, _ in START_ERAS}
                for s in starts:
                    era = next((lab for lab, lo, hi in START_ERAS if lo <= days[s] <= hi), None)
                    if era is None:
                        continue
                    units, cash, cash_level, parked = 1.0 / close[s], 0.0, None, False
                    for i in range(s + 1, s + WINDOW):
                        if want[i] and not parked:
                            moved = units * share
                            units -= moved
                            cash, cash_level, parked = moved * close[i] * (1 - half), level[i], True
                        elif not want[i] and parked:
                            units += cash * level[i] / cash_level * (1 - half) / close[i]
                            cash, parked = 0.0, False
                    end = s + WINDOW
                    value = units * close[end] + (cash * level[end] / cash_level if parked else 0.0)
                    res[era].append((value / (close[end] / close[s]) - 1) * 100)
                meds = {e: np.median(v) for e, v in res.items() if v}
                allv = [x for v in res.values() for x in v]
                ahead, worst = np.mean([x > 0 for x in allv]), min(allv)
                ok = all(m >= 0.5 for m in meds.values()) and ahead >= 0.6 and worst >= -5
                ok_all = ok_all and ok
                score.append(min(meds.values()))
                line.append(f"{cost_label}: {meds['2015-2019']:+5.1f}% | {meds['2020-2024']:+5.1f}%, ahead {ahead:3.0%}, worst {worst:+5.1f}%")
            verdicts[(pname, share)] = ok_all
            if best is None or min(score) > best[0]:
                best = (min(score), pname, share)
            moves = int(np.sum(np.diff(want.astype(int)) != 0))
            print(f"  {pname:<28} {share:>4.0%}  " + "   ".join(line) + f"   ({moves} moves in all)" + ("   WORTH FOLLOWING" if ok_all else ""))
    print("\nverdicts (decided before the run):")
    passed = [k for k, v in verdicts.items() if v]
    for pname, share in passed:
        print(f"  WORTH FOLLOWING: {pname}, {share:.0%} of the holding")
    if not passed:
        print(f"  NOT WORTH FOLLOWING; the closest: {best[1]}, {best[2]:.0%} (its weakest median {best[0]:+.1f}%)")
    i = n - 1
    print(f"\non {days[i]}: BOX {'on ' + str(tuple(round(x / 1e7, 2) for x in box18[i])) + 'M toman' if box18[i] else 'off'}; "
          f"ROOM RULE {'on' if room_rule[i] else 'off'}; the dollar's box {'on' if boxusd[i] else 'off'}")


if __name__ == "__main__":
    main()
