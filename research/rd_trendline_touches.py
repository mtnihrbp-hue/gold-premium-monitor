"""Resistance trend lines on 18K: does a line tested many times hold better than a short one? (SP-D,
SP_D_HANDOFF.md section 48; the owner, 2026-10-17: "the resistance line in the nightly chart. the previous one
was a long term one, this one is short term, i like the long term one more, why ? bacuse it has been tested
many times, argue ?")

caluclator/technical.trendlines draws, of every line through two confirmed swing highs of the last 120 days
that no close has crossed, the one closest above today's close. Touches do not count. Until 2026-10-08 that
was the line from 07-18 (19.15M) to 09-10 (24.37M), touched 4-5 times; from 10-12, once the high of 10-06 was
confirmed, the line from 09-10 to 10-06, touched twice.

Rules, fixed before the run:
- Data: tgju's daily 18K candles (geram18), every page, classified as production classifies them
  (validation.data.classify_daily_candle); a candle's range is read only when COMPLETE and not flat
  (main._usable).
- Lines: the chart's own (technical._pivots, SWING_WINDOW 5, TRENDLINE_LOOKBACK 120, TRENDLINE_TOLERANCE
  0.5%): every pair of confirmed swing highs whose line no close since the first has crossed by more than
  0.5%, and which stands at or above the day's close.
- A line's touches: the confirmed swing highs from its first point on that sit within 1% of it, its two
  points included. Its age: trading days since its first point. Its distance: its value over the close.
- Sample days: every 5th trading day from 2014-01-01 to 20 days before the last.
- On each sample day:
    A   the chart's rule: the valid line closest above the close
    B   the most touched valid line (ties: the closest)
    by touches: the closest valid line with 2, with 3, and with 4 or more touches
- Outcome: the line breaks when a close in the next 20 trading days stands more than 0.5% above the line's
  value that day. A held line that a high came within 1% of was tested and held. After a break, 18K's return
  over the 20 trading days from the breaking close, against every sample day's 20-day return.
- Reported by half (2014-2019, 2020-2026): for A and B, the days with a line, mean touches, age and
  distance, the break rate; by touches and by distance (0-3%, 3-8%, 8% or more), the lines and the break
  rate; the return after breaks by touches.
- Verdicts, decided now:
    TOUCHES MATTER   in both halves, in each distance band where both the 2-touch and the 4+-touch lines
                     number 30 or more, the 4+-touch lines broke at least 10 points less often; and there is
                     at least one such band in each half
    TOUCHES DO NOT   in both halves there is such a band, and none shows the 4+-touch lines breaking even 5
                     points less often
    MIXED            otherwise
  A vs B is reported, not judged: B's line usually sits farther away, so it breaks less for that reason alone.

Run: python research/rd_trendline_touches.py   (reads tgju from the workstation directly)
"""

import os
import sys
from datetime import date

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

AHEAD, TOUCH, STEP = 20, 0.01, 5
BANDS = ((0, 3), (3, 8), (8, 1000))
HALVES = (("2014-2019", date(2014, 1, 1), date(2019, 12, 31)), ("2020-2026", date(2020, 1, 1), date(2026, 12, 31)))


def load():
    import requests
    s = requests.Session()
    s.trust_env = False                                  # Iranian sites directly from the workstation
    requests.get = s.get
    from collector.tgju import fetch_daily_candles
    from validation.data import classify_daily_candle
    rows, start = [], 0
    while True:
        page = fetch_daily_candles("geram18", 1000, start=start, order="asc")
        rows += page
        if len(page) < 1000:
            break
        start += 1000
    seen = {}
    for r in rows:
        quality = classify_daily_candle(r)
        if quality != "INVALID":
            seen[date.fromisoformat(r["date"])] = (r, quality)
    days = sorted(seen)
    o, h, l, c = (np.array([float(seen[d][0][k]) for d in days]) for k in ("open", "high", "low", "close"))
    usable = [seen[d][1] == "COMPLETE" and not (o[j] == h[j] == l[j] == c[j]) for j, d in enumerate(days)]
    return days, h, c, usable


def lines_on(h, c, t, usable):
    from caluclator.technical import SWING_WINDOW, TRENDLINE_LOOKBACK, TRENDLINE_TOLERANCE, _pivots
    piv = _pivots(h, t, SWING_WINDOW, True, usable=usable, lookback=TRENDLINE_LOOKBACK)
    out = []
    for b in range(1, len(piv)):
        for a in range(b):
            i1, i2 = piv[a], piv[b]
            slope = (h[i2] - h[i1]) / (i2 - i1)
            line = h[i1] + slope * (np.arange(i1, t + 1) - i1)
            if not (np.all(c[i1:t + 1] <= line * (1 + TRENDLINE_TOLERANCE)) and line[-1] >= c[t]):
                continue
            touches = sum(1 for j in piv if j >= i1 and abs(h[j] / (h[i1] + slope * (j - i1)) - 1) <= TOUCH)
            out.append({"i1": i1, "slope": slope, "at": line[-1], "touches": touches, "age": t - i1,
                        "dist": (line[-1] / c[t] - 1) * 100})
    return out


def outcome(h, c, t, ln):
    from caluclator.technical import TRENDLINE_TOLERANCE
    tested = False
    for k in range(t + 1, t + AHEAD + 1):
        value = h[ln["i1"]] + ln["slope"] * (k - ln["i1"])
        if c[k] > value * (1 + TRENDLINE_TOLERANCE):
            after = (c[min(k + AHEAD, len(c) - 1)] / c[k] - 1) * 100 if k + AHEAD < len(c) else None
            return "broke", after
        if h[k] >= value * (1 - TOUCH):
            tested = True
    return ("tested and held" if tested else "held"), None


def bucket(touches):
    return "2" if touches == 2 else "3" if touches == 3 else "4+"


def main():
    days, h, c, usable = load()
    n = len(days)
    print(f"tgju 18K: {n} candles, {days[0]} to {days[-1]}")
    fwd = {t: (c[t + AHEAD] / c[t] - 1) * 100 for t in range(n - AHEAD)}
    rec = {name: {"A": [], "B": [], "by": {b: [] for b in ("2", "3", "4+")}, "all": []} for name, *_ in HALVES}
    start = next(i for i, d in enumerate(days) if d >= date(2014, 1, 1))
    for t in range(max(start, 130), n - AHEAD, STEP):
        half = next(name for name, lo, hi in HALVES if lo <= days[t] <= hi)
        rec[half]["all"].append(fwd[t])
        ls = lines_on(h, c, t, usable)
        if not ls:
            continue
        a = min(ls, key=lambda x: x["at"])
        b = min(ls, key=lambda x: (-x["touches"], x["at"]))
        for key, ln in (("A", a), ("B", b)):
            rec[half][key].append((ln, *outcome(h, c, t, ln)))
        for bk in ("2", "3", "4+"):
            pick = [x for x in ls if bucket(x["touches"]) == bk]
            if pick:
                ln = min(pick, key=lambda x: x["at"])
                rec[half]["by"][bk].append((ln, *outcome(h, c, t, ln)))
    verdict_rows = {}
    for half, *_ in HALVES:
        r = rec[half]
        print(f"\n{half}: {len(r['all'])} sample days; every sample day's 20-day return {np.mean(r['all']):+.2f}%")
        for key, label in (("A", "A, the chart's rule (closest)"), ("B", "B, the most touched")):
            x = r[key]
            if not x:
                continue
            print(f"  {label:32} {len(x):4} days with a line: touches {np.mean([l['touches'] for l, *_ in x]):.1f}, "
                  f"age {np.mean([l['age'] for l, *_ in x]):.0f} days, {np.mean([l['dist'] for l, *_ in x]):.1f}% above; "
                  f"broke within 20 days {np.mean([o == 'broke' for _, o, _ in x]):.0%}, "
                  f"tested and held {np.mean([o == 'tested and held' for _, o, _ in x]):.0%}")
        print("  by touches and distance (the closest line of each touch count; lines, broke within 20 days):")
        verdict_rows[half] = []
        for lo, hi in BANDS:
            cells, rates = [], {}
            for bk in ("2", "3", "4+"):
                x = [(l, o) for l, o, _ in r["by"][bk] if lo <= l["dist"] < hi]
                rates[bk] = (len(x), np.mean([o == "broke" for _, o in x]) if x else np.nan)
                cells.append(f"{bk} touches {len(x):4}, {rates[bk][1]:.0%}" if x else f"{bk} touches    0")
            print(f"    {lo}-{hi if hi < 1000 else ''}%".ljust(12) + " | ".join(cells))
            if rates["2"][0] >= 30 and rates["4+"][0] >= 30:
                verdict_rows[half].append((rates["2"][1] - rates["4+"][1]) * 100)
        print("  after a break, 18K over the next 20 days (by touches of the closest line):")
        for bk in ("2", "3", "4+"):
            after = [a for _, o, a in r["by"][bk] if o == "broke" and a is not None]
            if after:
                print(f"    {bk} touches: {len(after)} breaks, {np.mean(after):+.2f}% (every sample day {np.mean(r['all']):+.2f}%)")
    print("\nVERDICT")
    rows = verdict_rows
    if all(rows[h_] for h_, *_ in HALVES) and all(all(g >= 10 for g in rows[h_]) for h_, *_ in HALVES):
        print("  TOUCHES MATTER: in every comparable band of both halves, 4+-touch lines broke 10+ points less often")
    elif all(rows[h_] for h_, *_ in HALVES) and all(all(g < 5 for g in rows[h_]) for h_, *_ in HALVES):
        print("  TOUCHES DO NOT: in no comparable band did 4+-touch lines break even 5 points less often")
    else:
        print("  MIXED")
    print("  gaps (2-touch break rate minus 4+), by band:", {h_: [f"{g:+.0f}" for g in rows[h_]] for h_, *_ in HALVES})


if __name__ == "__main__":
    main()
