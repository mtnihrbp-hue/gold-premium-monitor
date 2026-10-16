"""How long to park in fixed income after a trend break, and does a reader who follows it end ahead?
(SP-D, SP_D_HANDOFF.md section 42; the owner, 2026-10-16: "how long park", then "Go ahead ... GO FULL
POWER".)

Section 41.4 found that 20 days in the fixed-income fund after a trend break beat holding 18K, in both
eras. It tested one length. This tests the length, the breaks together, a break with a warning, and the
whole record of a reader who follows the rule with its trading costs.

Rules, fixed before the run:
- Data: rd_falls.load() (tgju's daily 18K and dollar to the latest close; the fixed-income fund's level
  from 2015-03-15; section 41's signals).
- Breaks (an episode starts on the first day on, 10 trading days or more after the last start):
    B1  18K under its 50-day        B2  EMA20 under EMA50        B3  the dollar under its 50-day
    B4  any of the three            B5  18K and the dollar both under their 50-day
- Exits: after 10, 20, 40 or 60 trading days; UNTIL IT ENDS (the first day the break is off, after 3
  days at least, at most 120); UNTIL IT ENDS OR 40 days.
- Per episode, the gain of parking: the fund's growth over 18K's from the start to the exit, minus 1, in
  percent (above 0, parking paid). Per era (2015-2019, 2020-2026): the mean, the share that paid, the
  worst.
- With a warning: B4's episodes split by whether a dollar spike (+8% in 10 days) or turbulence was on
  at the start (section 41's definitions); the same exits.
- The reader's record: a reader starts all in gold, moves the whole holding (and, as the room does,
  40% of it) into the fund on a break's start, and back on the exit; one move at a time. Each move
  costs half a round trip: Daric's 0.30% and Goldika's 2.37%. Two-year windows starting every 20
  trading days from 2015-03-15; the end value against holding 18K. Reported by the windows' start era
  (2015-2019, 2020-2024): the median, the share of windows ahead, the worst.
- Verdicts, decided now:
    an exit PAYS for a break when its mean gain is above 0 in both eras and it paid in at least 55% of
      the episodes overall;
    a rule is WORTH FOLLOWING when, at both costs, its median over windows is at least +0.5 points
      above holding in both start eras, it is ahead in at least 60% of all windows, and its worst
      window is no lower than -5%.
- Reported beside them, not judged: which breaks are on at the latest close.

Run: python research/rd_parking.py   (reads tgju from the workstation directly)
"""

import os
import sys
from datetime import date
from statistics import mean

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rd_falls import load  # noqa: E402

GAP = 10
EXITS = ("10", "20", "40", "60", "until it ends", "until it ends or 40")
ERAS = (("2015-2019", date(2015, 3, 15), date(2019, 12, 31)), ("2020-2026", date(2020, 1, 1), date(2026, 12, 31)))
START_ERAS = (("2015-2019", date(2015, 3, 15), date(2019, 12, 31)), ("2020-2024", date(2020, 1, 1), date(2024, 12, 31)))
COSTS = (("Daric 0.30%", 0.0030), ("Goldika 2.37%", 0.0237))
WINDOW = 500           # about two years of trading days
STEP = 20


def starts_of(on):
    out, last = [], -10**9
    for i in range(1, len(on)):
        if on[i] and not on[i - 1] and i - last >= GAP:
            out.append(i)
            last = i
    return out


def exit_of(on, i, rule, n):
    if rule.isdigit():
        return min(i + int(rule), n - 1)
    cap = 40 if rule.endswith("40") else 120
    for t in range(i + 3, min(i + cap, n - 1) + 1):
        if not on[t]:
            return t
    return min(i + cap, n - 1)


def main():
    days, close, level, sig, _ = load()
    n = len(days)
    on = {
        "B1 18K under its 50-day": sig["18K under its 50-day"],
        "B2 EMA20 under EMA50": sig["EMA20 under EMA50"],
        "B3 the dollar under its 50-day": sig["the dollar under its 50-day"],
    }
    on["B4 any of the three"] = on["B1 18K under its 50-day"] | on["B2 EMA20 under EMA50"] | on["B3 the dollar under its 50-day"]
    on["B5 18K and the dollar both"] = on["B1 18K under its 50-day"] & on["B3 the dollar under its 50-day"]
    warning = sig["a dollar spike (+8% in 10d)"] | sig["turbulence"]
    usable = np.isfinite(level)

    def gain(i, t):
        return ((level[t] / level[i]) / (close[t] / close[i]) - 1) * 100

    print(f"{n} days {days[0]} .. {days[-1]}; the fund from {days[int(np.argmax(usable))]}")
    pays = {}
    print("\nPER EPISODE: the gain of parking, by exit (mean, paid, worst; 2015-2019 | 2020-2026)")
    groups = dict(on)
    groups["B4 with a warning"] = on["B4 any of the three"]
    groups["B4 without a warning"] = on["B4 any of the three"]
    for name, flag in groups.items():
        st = [i for i in starts_of(flag) if usable[i]]
        if name == "B4 with a warning":
            st = [i for i in st if warning[i]]
        elif name == "B4 without a warning":
            st = [i for i in st if not warning[i]]
        print(f"\n  {name} ({len(st)} episodes)")
        for rule in EXITS:
            cells, all_g, era_means = [], [], []
            for era, lo, hi in ERAS:
                g = []
                for i in st:
                    if lo <= days[i] <= hi:
                        t = exit_of(flag, i, rule, n)
                        if usable[t] and t > i:
                            g.append(gain(i, t))
                all_g += g
                era_means.append(mean(g) if g else None)
                cells.append(f"{mean(g):+5.2f}% {np.mean([x > 0 for x in g]):4.0%} {min(g):+6.1f}% (n={len(g):>2})"
                             if g else "no episodes")
            ok = all(m is not None and m > 0 for m in era_means) and all_g and np.mean([x > 0 for x in all_g]) >= 0.55
            pays[(name, rule)] = ok
            print(f"    exit {rule:<20} {cells[0]}  |  {cells[1]}  {'PAYS' if ok else ''}")

    print("\nTHE READER'S RECORD: two-year windows against holding 18K (median, ahead, worst; 2015-2019 | 2020-2024 starts)")
    worth = {}
    for name in on:
        for rule in ("20", "40", "until it ends", "until it ends or 40"):
            for share in (1.0, 0.4):
                ok_all = True
                line = []
                for cost_label, rt in COSTS:
                    half = rt / 2
                    starts = [s for s in range(n - WINDOW) if usable[s] and (s - int(np.argmax(usable))) % STEP == 0]
                    res = {e: [] for e, _, _ in START_ERAS}
                    for s in starts:
                        e = next((lab for lab, lo, hi in START_ERAS if lo <= days[s] <= hi), None)
                        if e is None:
                            continue
                        gold_units, cash, parked_until = 1.0 / close[s], 0.0, None
                        for i in range(s + 1, s + WINDOW):
                            if parked_until is None and on[name][i] and not on[name][i - 1] and usable[i]:
                                moved = gold_units * share
                                gold_units -= moved
                                cash += moved * close[i] * (1 - half)
                                parked_until = exit_of(on[name], i, rule, n)
                                cash_level = level[i]
                            elif parked_until is not None and i >= parked_until:
                                grown = cash * level[i] / cash_level
                                gold_units += grown * (1 - half) / close[i]
                                cash, parked_until = 0.0, None
                        end = s + WINDOW
                        if parked_until is not None:
                            cash = cash * level[end] / cash_level
                        value = gold_units * close[end] + cash
                        res[e].append((value / (1.0 / close[s] * close[end]) - 1) * 100)
                    meds = {e: (np.median(v) if v else np.nan) for e, v in res.items()}
                    allv = [x for v in res.values() for x in v]
                    ahead = np.mean([x > 0 for x in allv])
                    worst = min(allv)
                    ok = all(np.isfinite(m) and m >= 0.5 for m in meds.values()) and ahead >= 0.6 and worst >= -5
                    ok_all = ok_all and ok
                    line.append(f"{cost_label}: {meds['2015-2019']:+5.1f}% | {meds['2020-2024']:+5.1f}%, ahead {ahead:3.0%}, worst {worst:+5.1f}%")
                worth[(name, rule, share)] = ok_all
                print(f"  {name:<30} exit {rule:<20} {share:>4.0%}  " + "   ".join(line) + ("   WORTH FOLLOWING" if ok_all else ""))

    print("\nverdicts (decided before the run):")
    for (name, rule), ok in pays.items():
        if ok:
            print(f"  parking PAYS: {name}, exit {rule}")
    for (name, rule, share), ok in worth.items():
        if ok:
            print(f"  WORTH FOLLOWING: {name}, exit {rule}, {share:.0%} of the holding")
    if not any(worth.values()):
        print("  no rule is worth following on the reader's record")
    print(f"\nat the latest close ({days[-1]}): " + "; ".join(f"{k} {'ON' if v[-1] else 'off'}" for k, v in on.items()))


if __name__ == "__main__":
    main()
