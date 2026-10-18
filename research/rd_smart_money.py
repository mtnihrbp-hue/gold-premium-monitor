"""Smart money in the gold funds: big individual tickets, as Iran's screens read them (SP-D, SP_D_HANDOFF.md
section 48; the owner, 2026-10-17: "do an R&D for hot money or smart money. maybe we can find something there
that gives us a hint").

Measured before: the funds' money in and out (46.1, 47.1), their real creations and redemptions on fipiran and
their premium (25), the session's volume, order book and big trades (24), a rush of buyers (41.4). Not
measured: the per-head screen Iran's traders call smart money -- days when individual buyers come with much
bigger tickets than usual and outweigh the sellers ("سرانه خرید" and "قدرت خریدار").

Rules, fixed before the run:
- Data: the gold funds' daily individual trading (src/seed/gold_fund_daily.json: buy value, buyers, sell
  value, sellers, summed over the 19 funds, 2017-07 to 2026-10-17); tgju's daily 18K closes (live,
  research/rd_news_events.series).
- A day's per-head buy: buy value over buyers; per-head sell: sell value over sellers; buyer power: per-head
  buy over per-head sell.
- Each ranked against its own previous 250 fund days (at least 100).
- Detectors, each on or off at a fund day:
    BIG BUYERS        per-head buy in the top 5% of its year
    BIG SELLERS       per-head sell in the top 5% of its year
    BUYERS IN CONTROL buyer power in the top 5% of its year
    SELLERS IN CONTROL buyer power in the bottom 5% of its year
    SMART MONEY IN    BIG BUYERS and BUYERS IN CONTROL on the same day
- Outcomes, from the fund day's 18K close (or the last tgju close before it): the return over the next 1, 5
  and 20 tgju days; higher after 5 and after 20; a fall of 5% or more within 20 days.
- Episodes: a detector's episode starts on its first day on, 10 fund days or more after its last start.
- Halves: the days with ranks, split at their middle day; every day's rates in each half are the control.
- Verdicts, decided now (each needs 10 episodes or more in each half):
    MEETS THE OWNER'S 90%  18K moved the detector's way (higher after the buyers' three, lower after the
                   sellers' two) over 5 days, or over 20, in at least 90% of its episodes in both halves
    WARNS          its 5%-fall rate is at least 1.5 times every day's in both halves
    LEANS UP/DOWN  its mean 20-day return is at least 1.5 points above / below every day's in both halves
    DESCRIBES ONLY otherwise
  Five detectors are tried, so one verdict in five may be luck: a verdict here is a lead to confirm on the
  days after 2026-10-17, not a rule.

Run: python research/rd_smart_money.py   (reads tgju from the workstation directly)
"""

import json
import os
import sys
from bisect import bisect_right
from datetime import date

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "src"))
from rd_news_events import series  # noqa: E402

YEAR, MIN_RANK, TAIL = 250, 100, 5
GAP, FALL, BAR, MIN_EP = 10, -0.05, 0.90, 10
UP = {"BIG BUYERS", "BUYERS IN CONTROL", "SMART MONEY IN"}


def ranks(x):
    out = np.full(len(x), np.nan)
    for i in range(len(x)):
        h = x[max(0, i - YEAR):i]
        h = h[np.isfinite(h)]
        if len(h) >= MIN_RANK and np.isfinite(x[i]):
            out[i] = np.mean(h < x[i]) * 100
    return out


def main():
    seed = json.load(open(os.path.join(HERE, "..", "src", "seed", "gold_fund_daily.json"), encoding="utf-8"))
    fdays = sorted(date.fromisoformat(k) for k in seed["days"])
    a = np.array([seed["days"][d.isoformat()][:4] for d in fdays], dtype=float)
    head_buy, head_sell = a[:, 0] / a[:, 1], a[:, 2] / a[:, 3]
    power = head_buy / head_sell
    rb, rs, rp = ranks(head_buy), ranks(head_sell), ranks(power)
    on = {"BIG BUYERS": rb >= 100 - TAIL, "BIG SELLERS": rs >= 100 - TAIL,
          "BUYERS IN CONTROL": rp >= 100 - TAIL, "SELLERS IN CONTROL": rp < TAIL}
    on["SMART MONEY IN"] = on["BIG BUYERS"] & on["BUYERS IN CONTROL"]
    have = [i for i in range(len(fdays)) if np.isfinite(rb[i]) and np.isfinite(rp[i])]

    gold = series("geram18")
    gdays = sorted(gold)
    close = np.array([gold[d] for d in gdays])
    path = {}
    for i in have:
        k = bisect_right(gdays, fdays[i]) - 1
        if k < 0 or (fdays[i] - gdays[k]).days > 7 or k + 20 >= len(gdays):
            continue
        path[i] = {h: (close[k + h] / close[k] - 1) * 100 for h in (1, 5, 20)}
        path[i]["fell"] = float(close[k + 1:k + 21].min() / close[k] - 1 <= FALL)

    mid = have[len(have) // 2]
    halves = (("first half", have[0], mid), ("second half", mid, have[-1] + 1))
    print(f"fund days with ranks {fdays[have[0]]} to {fdays[have[-1]]}; halves split at {fdays[mid]}")
    base = {}
    for name, lo, hi in halves:
        idx = [i for i in range(lo, hi) if i in path]
        base[name] = {h: np.mean([path[i][h] for i in idx]) for h in (1, 5, 20)}
        base[name].update(up5=np.mean([path[i][5] > 0 for i in idx]), up20=np.mean([path[i][20] > 0 for i in idx]),
                          fell=np.mean([path[i]["fell"] for i in idx]))
        b = base[name]
        print(f"EVERY DAY {name:11}: 1d {b[1]:+.2f}%, 5d {b[5]:+.2f}%, 20d {b[20]:+.2f}%; higher after 5d {b['up5']:.0%}, "
              f"after 20d {b['up20']:.0%}; 5% fall {b['fell']:.0%}")
    verdicts = {}
    for key, flags in on.items():
        eps, last = [], -10 ** 9
        for i in have:
            if flags[i] and (i == 0 or not flags[i - 1]) and i - last >= GAP:
                eps.append(i)
                last = i
        print(f"\n{key}: {len(eps)} episodes")
        rows = []
        for name, lo, hi in halves:
            e = [i for i in eps if lo <= i < hi and i in path]
            if not e:
                print(f"  {name:11}   0 episodes")
                rows.append(None)
                continue
            m = {h: np.mean([path[i][h] for i in e]) for h in (1, 5, 20)}
            up5, up20 = np.mean([path[i][5] > 0 for i in e]), np.mean([path[i][20] > 0 for i in e])
            way5, way20 = (up5, up20) if key in UP else (1 - up5, 1 - up20)
            fell = np.mean([path[i]["fell"] for i in e])
            b = base[name]
            print(f"  {name:11} {len(e):3} episodes: 1d {m[1]:+.2f}%, 5d {m[5]:+.2f}%, 20d {m[20]:+.2f}% (every day "
                  f"{b[20]:+.2f}%); its way after 5d {way5:.0%}, after 20d {way20:.0%}; 5% fall {fell:.0%} "
                  f"(every day {b['fell']:.0%})")
            rows.append((len(e), m[20] - b[20], fell / b["fell"] if b["fell"] else np.nan, way5, way20))
        enough = all(r is not None and r[0] >= MIN_EP for r in rows)
        v = []
        if enough and (all(r[3] >= BAR for r in rows) or all(r[4] >= BAR for r in rows)):
            v.append("MEETS THE OWNER'S 90%")
        if enough and all(r[2] >= 1.5 for r in rows):
            v.append("WARNS")
        if enough and all(r[1] >= 1.5 for r in rows):
            v.append("LEANS UP")
        if enough and all(r[1] <= -1.5 for r in rows):
            v.append("LEANS DOWN")
        verdicts[key] = ", ".join(v) or ("DESCRIBES ONLY" + ("" if enough else " (fewer than 10 episodes in a half)"))
        recent = [fdays[i] for i in eps if fdays[i] >= date(2025, 10, 1)]
        if recent:
            print("  since 2025-10: " + ", ".join(
                f"{d} ({path[fdays.index(d)][20]:+.1f}% in 20d)" if fdays.index(d) in path else f"{d} (not yet 20d)"
                for d in recent))
    print("\nVERDICTS")
    for key, v in verdicts.items():
        print(f"  {key:18} {v}")


if __name__ == "__main__":
    main()
