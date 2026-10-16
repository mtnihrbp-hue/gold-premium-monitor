"""WHEN, as a reader faces it: rial to convert into 18K within a month. Which rule pays less than buying
at once? (SP-D, SP_D_HANDOFF.md section 40; the owner, 2026-10-16: "R&D models, build scenarios and come
up with some suggestion for decision engine".)

The decision engine waits for a discount that is unusual and widening. 39.3 measured it on two months of
hourly readings (no better moments; waiting for its BUY cost 2%). This tests the families of rule a
decision engine could use, on 18K's own daily record since 2014, so each is judged across several
markets, not one rising one.

Rules, fixed before the run:
- Data: research/data/tgju_history.json, tgju's daily closes: 18K (geram18), the dollar
  (price_dollar_rl), world gold (ons, taken from the previous day, as the room does). The fair gap: 18K
  against world gold x the dollar x 0.75 / 31.1035, minus 1. Its rank: against the trailing 250 days.
- The reader: on an entry day, holds rial to convert within N = 20 trading days; the last day is a
  forced purchase. Price paid: that day's close; for a split, the mean of its parts' closes.
- Entries: every 20th trading day from the first with 250 days of history (independent windows); all
  trading days are reported beside them as context.
- Carry: rial waiting can sit in fixed income. Reported without carry, and with carry from 2015-03-15,
  where src/seed/fixed_income.json starts (the fund's level grows the waiting cash).
- Rules (first day t in the window that meets the condition; otherwise day N):
    S0  buy now                                   day 0
    S1  wait for a dip of 2 / 3 / 5%              close <= day 0's close x (1 - d)
    S2  wait for a deep gap                       the fair gap's rank <= 20%
    S3  wait out a 50-day break                   day 0 if 18K >= its 50-day; else the first close >= it
    S4  wait out the dollar's 50-day break        day 0 if the dollar >= its 50-day; else first >= it
    S5  split in four                             days 0, 5, 10, 15, a quarter each
    S6  do not buy when less discounted than usual   day 0 unless the gap's rank >= 80%; then the first
                                                  day with rank <= 50%
    S7  do not catch a falling knife              day 0 unless 18K fell 3% or more in 5 days; then the
                                                  first day that closes above the day before
    S8  the engine's shape, daily                 the first day the gap's rank <= 20% and the gap
                                                  widened since the day before (CHEAP and IMPROVING)
- Cost: price paid / buying at once - 1, in percent (above 0, the rule paid more). Reported: mean,
  median, the share of windows cheaper than buying at once, the 90th percentile (a bad case), the worst;
  for 2014-2019, 2020-2026 and the last two years.
- Verdict, decided now, on the carry figures: a rule BEATS buying at once when its mean cost is below 0
  in both eras and it is cheaper in at least half the windows of each; it COSTS when its mean is above 0
  in both eras; else MIXED.

Run: python research/rd_when_scenarios.py
"""

import json
import os
from datetime import date
from statistics import mean, median

HERE = os.path.dirname(os.path.abspath(__file__))
N = 20
RANK_DAYS = 250
STEP = 20
ERAS = (("2014-2019", date(2014, 1, 1), date(2019, 12, 31)), ("2020-2026", date(2020, 1, 1), date(2026, 12, 31)))


def load():
    raw = json.load(open(os.path.join(HERE, "data", "tgju_history.json"), encoding="utf-8"))
    series = {k: {date.fromisoformat(r["date"]): float(r["close"]) for r in raw[k]} for k in ("geram18", "price_dollar_rl", "ons")}
    days = sorted(series["geram18"])
    gold, usd, ons = series["geram18"], series["price_dollar_rl"], series["ons"]

    # aligned series: dollar on or before the day, world gold strictly before it
    import bisect
    usd_days, ons_days = sorted(usd), sorted(ons)
    rows = []
    for d in days:
        i = bisect.bisect_right(usd_days, d) - 1
        j = bisect.bisect_left(ons_days, d) - 1
        if i < 0 or j < 0:
            continue
        u, w = usd[usd_days[i]], ons[ons_days[j]]
        fair = w * u * 0.75 / 31.1035
        rows.append({"day": d, "close": gold[d], "usd": u, "gap": gold[d] / fair - 1})
    fi = json.load(open(os.path.join(HERE, "..", "src", "seed", "fixed_income.json"), encoding="utf-8"))["level"]
    fi = {date.fromisoformat(k): float(v) for k, v in fi.items()}
    fi_days = sorted(fi)
    for r in rows:
        k = bisect.bisect_right(fi_days, r["day"]) - 1
        r["fi"] = fi[fi_days[k]] if k >= 0 and r["day"] >= fi_days[0] else None
    return rows


def enrich(rows):
    closes, usds, gaps = [r["close"] for r in rows], [r["usd"] for r in rows], [r["gap"] for r in rows]
    for i, r in enumerate(rows):
        r["sma50"] = mean(closes[i - 49:i + 1]) if i >= 49 else None
        r["usd50"] = mean(usds[i - 49:i + 1]) if i >= 49 else None
        window = gaps[max(0, i - RANK_DAYS):i]
        r["rank"] = (sum(g < r["gap"] for g in window) / len(window)) if len(window) >= RANK_DAYS else None
        r["fell5"] = (closes[i] / closes[i - 5] - 1) if i >= 5 else None


def choose(rows, i, rule):
    """The day index a rule buys on, for an entry at i (None for a split)."""
    end = i + N
    r0 = rows[i]
    if rule == "S0":
        return i
    if rule.startswith("S1"):
        d = {"S1-2%": 0.02, "S1-3%": 0.03, "S1-5%": 0.05}[rule]
        return next((t for t in range(i + 1, end + 1) if rows[t]["close"] <= r0["close"] * (1 - d)), end)
    if rule == "S2":
        return next((t for t in range(i, end + 1) if rows[t]["rank"] is not None and rows[t]["rank"] <= 0.20), end)
    if rule == "S3":
        if r0["close"] >= r0["sma50"]:
            return i
        return next((t for t in range(i + 1, end + 1) if rows[t]["close"] >= rows[t]["sma50"]), end)
    if rule == "S4":
        if r0["usd"] >= r0["usd50"]:
            return i
        return next((t for t in range(i + 1, end + 1) if rows[t]["usd"] >= rows[t]["usd50"]), end)
    if rule == "S6":
        if r0["rank"] is None or r0["rank"] < 0.80:
            return i
        return next((t for t in range(i + 1, end + 1) if rows[t]["rank"] is not None and rows[t]["rank"] <= 0.50), end)
    if rule == "S7":
        if r0["fell5"] is None or r0["fell5"] > -0.03:
            return i
        return next((t for t in range(i + 1, end + 1) if rows[t]["close"] > rows[t - 1]["close"]), end)
    if rule == "S8":
        return next((t for t in range(max(i, 1), end + 1) if rows[t]["rank"] is not None and rows[t]["rank"] <= 0.20
                     and rows[t]["gap"] < rows[t - 1]["gap"]), end)
    raise ValueError(rule)


def paid(rows, i, rule, carry):
    """Price paid per rial of day 0, as a multiple of buying at once (1.0 = the same)."""
    r0 = rows[i]

    def grown(t):
        if not carry or t == i:
            return 1.0
        a, b = r0["fi"], rows[t]["fi"]
        return (b / a) if a and b else None

    if rule == "S5":
        parts = []
        for t in (i, i + 5, i + 10, i + 15):
            g = grown(t)
            if g is None:
                return None
            parts.append(rows[t]["close"] / g)       # the waiting quarter grew, so it buys more
        return mean(parts) / r0["close"]
    t = choose(rows, i, rule)
    g = grown(t)
    return None if g is None else rows[t]["close"] / g / r0["close"]


RULES = ("S0", "S1-2%", "S1-3%", "S1-5%", "S2", "S3", "S4", "S5", "S6", "S7", "S8")
NAMES = {"S0": "buy now", "S1-2%": "wait for a 2% dip", "S1-3%": "wait for a 3% dip", "S1-5%": "wait for a 5% dip",
         "S2": "wait for a deep gap", "S3": "wait out an 18K 50-day break", "S4": "wait out a dollar 50-day break",
         "S5": "split in four weeks", "S6": "skip less-discounted days", "S7": "skip a falling knife",
         "S8": "the engine's shape (deep and widening)"}


def summarise(costs):
    if not costs:
        return None
    s = sorted(costs)
    return {"n": len(s), "mean": mean(s), "median": median(s), "cheaper": sum(c < 0 for c in s) / len(s),
            "p90": s[int(0.9 * (len(s) - 1))], "worst": s[-1]}


def main():
    rows = load()
    enrich(rows)
    first = next(i for i, r in enumerate(rows) if r["rank"] is not None and r["sma50"] is not None)
    last = len(rows) - N - 1
    print(f"{len(rows)} days {rows[0]['day']} .. {rows[-1]['day']}; entries from {rows[first]['day']} to {rows[last]['day']}")
    two_years = rows[-1]["day"].replace(year=rows[-1]["day"].year - 2)
    verdicts = {}
    for carry in (False, True):
        print(f"\n=== {'with' if carry else 'without'} fixed-income carry while waiting "
              f"({'from 2015-03-15' if carry else 'all entries'}); cost against buying at once, independent windows")
        print(f"{'rule':<42}{'era':<11}{'n':>4}{'mean':>8}{'median':>8}{'cheaper':>9}{'p90':>8}{'worst':>8}")
        for rule in RULES[1:]:
            per_era = {}
            for era, lo, hi in ERAS + (("last 2 yrs", two_years, date(2100, 1, 1)),):
                costs = []
                for i in range(first, last + 1, STEP):
                    if not (lo <= rows[i]["day"] <= hi):
                        continue
                    p = paid(rows, i, rule, carry)
                    if p is not None:
                        costs.append((p - 1) * 100)
                s = summarise(costs)
                per_era[era] = s
                if s:
                    print(f"{NAMES[rule]:<42}{era:<11}{s['n']:>4}{s['mean']:>+7.2f}%{s['median']:>+7.2f}%"
                          f"{s['cheaper']:>8.0%}{s['p90']:>+7.2f}%{s['worst']:>+7.2f}%")
            if carry:
                a, b = per_era["2014-2019"], per_era["2020-2026"]
                both = [x for x in (a, b) if x]
                allc = [c for x in both for c in [x["cheaper"]]]
                if len(both) == 2 and a["mean"] < 0 and b["mean"] < 0 and min(allc) >= 0.5:
                    verdicts[rule] = "BEATS buying at once"
                elif len(both) == 2 and a["mean"] > 0 and b["mean"] > 0:
                    verdicts[rule] = "COSTS more than buying at once"
                else:
                    verdicts[rule] = "MIXED"
    # all trading days, as context
    print("\ncontext: every trading day as an entry (overlapping windows), with carry")
    for rule in RULES[1:]:
        costs = [((paid(rows, i, rule, True) or 0) - 1) * 100 for i in range(first, last + 1) if paid(rows, i, rule, True)]
        s = summarise(costs)
        print(f"  {NAMES[rule]:<42} n={s['n']:>5} mean {s['mean']:+.2f}% median {s['median']:+.2f}% cheaper {s['cheaper']:.0%}")
    print("\nverdicts (with carry, decided before the run):")
    for rule in RULES[1:]:
        print(f"  {NAMES[rule]:<42} {verdicts[rule]}")


if __name__ == "__main__":
    main()
