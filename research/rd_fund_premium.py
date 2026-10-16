"""The gold fund's price against its own NAV: buyers paying up, sellers giving way (SP-D, SP_D_HANDOFF.md
section 42; the owner, 2026-10-16: "how can the gold etf money flow help").

The money-flow member counted who bought and sold (individuals' value and numbers). A fund's price against
its net asset value says how much they paid for it: a premium is buyers overpaying for gold, a discount
sellers accepting less. For Ayyar (عیار مفید, the largest gold fund), the price against the NAV chained from
fipiran's daily returns read 1.22 in July 2020, 0.90 in April 2025 and 1.10 in October 2026.

Rules, fixed before the run:
- The fund: Ayyar. Its price: tsetmc's final price (research/data/tsetmc_gold_funds.json). Its NAV: fipiran's
  daily NAV return chained from the fund's first day (research/data/fipiran_nav.json, 11586). The premium:
  price index / NAV index - 1, both from 1 on the first common day. It is relative: the chain's rounding
  drifts, so its rank against the trailing 250 trading days is what is used.
- The market: tgju's daily 18K (live, rd_news_events.series), and the fixed-income fund for parking
  (src/seed/fixed_income.json), as in rd_falls.py.
- Signals, at the premium's day (the 18K day on or after it): HIGH, rank >= 90%; LOW, rank <= 10%;
  episodes start on the first day in, 10 trading days or more after the last start.
- Outcomes on 18K: a 5% fall within 20 trading days; the 20-day return; parking 20 days in the fund
  against holding.
- Eras: 2019-2022 and 2023-2026 (the rank needs a year of the fund).
- Verdicts, decided now:
    HIGH WARNS when the 5%-fall rate after its episodes is at least 1.5 times every day's, in both eras,
      with at least 8 episodes in each;
    LOW PRECEDES RISES when the 20-day return after its episodes is at least 2 points above every day's,
      in both eras, with at least 8 episodes in each.
- Reported, not judged: the premium's rank on the latest day.

Run: python research/rd_fund_premium.py   (reads tgju from the workstation directly)
"""

import json
import os
import sys
from bisect import bisect_left, bisect_right
from datetime import date

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rd_news_events import series  # noqa: E402

AHEAD, GAP = 20, 10
ERAS = (("2019-2022", date(2019, 1, 1), date(2022, 12, 31)), ("2023-2026", date(2023, 1, 1), date(2026, 12, 31)))


def premium_series():
    nav = json.load(open(os.path.join(HERE, "data", "fipiran_nav.json"), encoding="utf-8"))["11586"]["items"]
    tse = next(v for v in json.load(open(os.path.join(HERE, "data", "tsetmc_gold_funds.json"), encoding="utf-8")).values()
               if v["symbol"] == "عيار")
    chain, level = {}, 1.0
    for it in sorted(nav, key=lambda x: x["date"]):
        level *= 1 + it["daily"] / 100
        chain[date.fromisoformat(it["date"])] = level
    px = {}
    for p in tse["prices"]:
        if p["final"] > 0:
            px[date(int(p["date"][:4]), int(p["date"][4:6]), int(p["date"][6:]))] = float(p["final"])
    common = sorted(set(chain) & set(px))
    p0, n0 = px[common[0]], chain[common[0]]
    days = common
    prem = np.array([(px[d] / p0) / (chain[d] / n0) - 1 for d in days])
    rank = np.full(len(prem), np.nan)
    for i in range(250, len(prem)):
        rank[i] = np.mean(prem[i - 250:i] < prem[i])
    return days, prem, rank


def main():
    pdays, prem, prank = premium_series()
    gold = series("geram18")
    gdays = sorted(gold)
    close = np.array([gold[d] for d in gdays])
    fi = json.load(open(os.path.join(HERE, "..", "src", "seed", "fixed_income.json"), encoding="utf-8"))["level"]
    fdays = sorted(date.fromisoformat(k) for k in fi)
    level = np.array([fi[fdays[bisect_right(fdays, d) - 1].isoformat()] if bisect_right(fdays, d) else np.nan for d in gdays],
                     dtype=float)
    n = len(gdays)
    # the premium's rank on each 18K day: the fund's last reading on or before it, within 7 days
    r18 = np.full(n, np.nan)
    for i, d in enumerate(gdays):
        k = bisect_right(pdays, d) - 1
        if k >= 0 and (d - pdays[k]).days <= 7:
            r18[i] = prank[k]
    fell = np.full(n, np.nan)
    ret = np.full(n, np.nan)
    park = np.full(n, np.nan)
    for i in range(n - AHEAD):
        fell[i] = float(close[i + 1:i + AHEAD + 1].min() / close[i] - 1 <= -0.05)
        ret[i] = (close[i + AHEAD] / close[i] - 1) * 100
        if np.isfinite(level[i]) and np.isfinite(level[i + AHEAD]):
            park[i] = ((level[i + AHEAD] / level[i]) / (close[i + AHEAD] / close[i]) - 1) * 100
    print(f"Ayyar's premium from {pdays[0]} to {pdays[-1]} ({len(pdays)} days); ranked from {pdays[250]}")
    verdict = {"HIGH": [], "LOW": []}
    for side, test in (("HIGH", lambda r: r >= 0.9), ("LOW", lambda r: r <= 0.1)):
        on = np.array([np.isfinite(r) and test(r) for r in r18])
        starts, last = [], -10**9
        for i in range(1, n - AHEAD):
            if on[i] and not on[i - 1] and i - last >= GAP:
                starts.append(i)
                last = i
        print(f"\n{side} (rank {'>= 90%' if side == 'HIGH' else '<= 10%'}): {len(starts)} episodes")
        for era, lo, hi in ERAS:
            idx = [i for i in starts if lo <= gdays[i] <= hi]
            base = [i for i in range(n - AHEAD) if lo <= gdays[i] <= hi and np.isfinite(r18[i])]
            if not idx:
                print(f"  {era}: no episodes")
                verdict[side].append(False)
                continue
            rate, brate = np.mean(fell[idx]), np.nanmean(fell[base])
            r, br = np.mean(ret[idx]), np.nanmean(ret[base])
            pk = np.nanmean(park[idx])
            print(f"  {era}: {len(idx):>2} episodes; a 5% fall after {rate:.0%} (every day {brate:.0%}); 20d return "
                  f"{r:+.1f}% ({br:+.1f}%); parking {pk:+.2f}%")
            if side == "HIGH":
                verdict[side].append(len(idx) >= 8 and rate >= 1.5 * brate)
            else:
                verdict[side].append(len(idx) >= 8 and r >= br + 2)
    print("\nverdicts (decided before the run):")
    print(f"  HIGH {'WARNS' if all(verdict['HIGH']) else 'does not warn'}")
    print(f"  LOW {'PRECEDES RISES' if all(verdict['LOW']) else 'does not precede rises'}")
    print(f"\nthe premium on {pdays[-1]}: {prem[-1] * 100:+.1f}% (relative), rank {prank[-1]:.0%} of its past year")


if __name__ == "__main__":
    main()
