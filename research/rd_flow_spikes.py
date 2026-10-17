"""Sudden moves in the gold funds' money: can they be seen, how often, and what followed (SP-D,
SP_D_HANDOFF.md section 47; the owner, 2026-10-17: "a sudden rush in gold etf trends, can we measure this
and report it ... so the buy sell in gold etfs has a momentum, then suddenly it jumps up, or there is a
range down, and then a push msg even can be sent, is this good ? and also is it possible to be drafted
accurately (more than 90% assurance)").

Rules, fixed before the run:
- Data: the 18 gold funds' daily individual trading (src/seed/gold_fund_daily.json, 2017-07-30 to
  2026-10-03); tgju's daily 18K closes (live, research/rd_news_events.series).
- A fund day's net money: individuals' buy value minus their sell value, summed over the funds; its
  buyers: individuals buying, summed.
- Five detectors, each on or off at a fund day:
    MONEY JUMP     the day's net is 3 standard deviations or more above the mean of the 20 fund days
                   before it (sudden, against its own momentum)
    MONEY DROP     3 or more below
    MONEY TOP 2%   the day's net ranks in the top 2% of the 250 fund days before it (large for the year)
    MONEY BOTTOM 2%  in the bottom 2%
    BUYERS JUMP    the day's buyers are 3 standard deviations or more above the mean of the 20 days before
- Episodes: a detector's episode starts on its first day on, 10 fund days or more after its last start.
- The day itself: 18K's move into the fund day (tgju's close on it, or the last before it, against the
  close before that) and over the 5 tgju days before, against every day's: does money follow the price?
- Outcomes, from that close: 18K's return over the next 1, 5 and 20 tgju days; higher after 5 and after 20
  days; a fall of 5% or more within 20 (the lowest close of t+1..t+20 at least 5% under t's).
- Halves: the fund days on which the 20-day mean is defined, split at their middle day. Every day's rates
  in each half are the control.
- Reported per detector and half: episodes, episodes a year, the day itself, the outcomes, the control.
- Verdicts, decided now:
    MEETS THE OWNER'S 90%  in both halves, with 10 episodes or more in each, 18K moved the detector's way
                   (higher after a jump or a top, lower after a drop or a bottom) over 5 days, or over 20,
                   in at least 90% of its episodes
    WARNS          its 5%-fall rate is at least 1.5 times every day's in both halves, 10 episodes or more each
    LEANS UP/DOWN  its mean 20-day return is at least 1.5 points above / below every day's in both halves,
                   10 episodes or more each
    DESCRIBES ONLY otherwise
  A detector may carry more than one verdict; DESCRIBES ONLY only when it carries none.

Run: python research/rd_flow_spikes.py   (reads tgju from the workstation directly)
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

LOOK, YEAR, Z, TAIL = 20, 250, 3.0, 2
GAP, FALL = 10, -0.05
HORIZONS = (1, 5, 20)
BAR, MIN_EP = 0.90, 10
UP = {"MONEY JUMP", "MONEY TOP 2%", "BUYERS JUMP"}


def detectors(a):
    n = len(a)
    net, buyers = a[:, 0] - a[:, 2], a[:, 1]
    on = {k: np.zeros(n, dtype=bool) for k in ("MONEY JUMP", "MONEY DROP", "MONEY TOP 2%", "MONEY BOTTOM 2%",
                                                 "BUYERS JUMP")}
    defined = np.zeros(n, dtype=bool)
    for i in range(LOOK, n):
        h, b = net[i - LOOK:i], buyers[i - LOOK:i]
        defined[i] = True
        if h.std() > 0:
            z = (net[i] - h.mean()) / h.std()
            on["MONEY JUMP"][i], on["MONEY DROP"][i] = z >= Z, z <= -Z
        if b.std() > 0:
            on["BUYERS JUMP"][i] = (buyers[i] - b.mean()) / b.std() >= Z
        if i >= YEAR:
            rank = np.mean(net[i - YEAR:i] < net[i]) * 100
            on["MONEY TOP 2%"][i], on["MONEY BOTTOM 2%"][i] = rank >= 100 - TAIL, rank < TAIL
    return on, defined


def gold_paths(fdays):
    gold = series("geram18")
    gdays = sorted(gold)
    close = np.array([gold[d] for d in gdays])
    out = {}
    for d in fdays:
        k = bisect_right(gdays, d) - 1
        if k < 6 or (d - gdays[k]).days > 7 or k + max(HORIZONS) >= len(gdays):
            continue
        out[d] = {
            "day": (close[k] / close[k - 1] - 1) * 100,
            "before5": (close[k - 1] / close[k - 6] - 1) * 100,
            **{h: (close[k + h] / close[k] - 1) * 100 for h in HORIZONS},
            "fell": float(close[k + 1:k + 21].min() / close[k] - 1 <= FALL),
        }
    return out


def episodes(flags):
    out, last = [], -10 ** 9
    for i in range(len(flags)):
        if flags[i] and (i == 0 or not flags[i - 1]) and i - last >= GAP:
            out.append(i)
            last = i
    return out


def stats(paths, ds):
    p = [paths[d] for d in ds if d in paths]
    if not p:
        return None
    return {"n": len(p), "day": np.mean([x["day"] for x in p]), "before5": np.mean([x["before5"] for x in p]),
            **{h: np.mean([x[h] for x in p]) for h in HORIZONS},
            "up5": np.mean([x[5] > 0 for x in p]), "up20": np.mean([x[20] > 0 for x in p]),
            "fell": np.mean([x["fell"] for x in p])}


def main():
    seed = json.load(open(os.path.join(HERE, "..", "src", "seed", "gold_fund_daily.json"), encoding="utf-8"))
    fdays = sorted(date.fromisoformat(k) for k in seed["days"])
    a = np.array([seed["days"][d.isoformat()][:4] for d in fdays], dtype=float)
    on, defined = detectors(a)
    paths = gold_paths(fdays)
    have = [i for i in range(len(fdays)) if defined[i]]
    mid = have[len(have) // 2]
    halves = (("first half", have[0], mid), ("second half", mid, len(fdays)))
    years = {name: (fdays[min(hi, len(fdays)) - 1] - fdays[lo]).days / 365.25 for name, lo, hi in halves}
    print(f"fund days {fdays[have[0]]} to {fdays[-1]}; halves split at {fdays[mid]}")
    base = {}
    for name, lo, hi in halves:
        base[name] = stats(paths, [fdays[i] for i in range(lo, hi)])
        b = base[name]
        print(f"EVERY DAY {name:11} 18K into the day {b['day']:+.2f}%, 5 days before {b['before5']:+.2f}%; after: "
              f"1d {b[1]:+.2f}%, 5d {b[5]:+.2f}%, 20d {b[20]:+.2f}%; higher after 5d {b['up5']:.0%}, after 20d "
              f"{b['up20']:.0%}; 5% fall {b['fell']:.0%}")
    verdicts = {}
    for k, flags in on.items():
        eps = episodes(flags)
        print(f"\n{k}: {len(eps)} episodes")
        rows = []
        for name, lo, hi in halves:
            s = stats(paths, [fdays[i] for i in eps if lo <= i < hi])
            if s is None:
                print(f"  {name:11}   0 episodes")
                rows.append(None)
                continue
            b = base[name]
            way5 = s["up5"] if k in UP else 1 - s["up5"]
            way20 = s["up20"] if k in UP else 1 - s["up20"]
            print(f"  {name:11} {s['n']:3} episodes ({s['n'] / years[name]:.1f} a year): 18K into the day "
                  f"{s['day']:+.2f}%, 5 days before {s['before5']:+.2f}%; after: 1d {s[1]:+.2f}%, 5d {s[5]:+.2f}%, "
                  f"20d {s[20]:+.2f}% (every day {b[20]:+.2f}%); its way after 5d {way5:.0%}, after 20d {way20:.0%}; "
                  f"5% fall {s['fell']:.0%} (every day {b['fell']:.0%})")
            rows.append((s, b, way5, way20))
        enough = all(r is not None and r[0]["n"] >= MIN_EP for r in rows)
        v = []
        if enough and (all(r[2] >= BAR for r in rows) or all(r[3] >= BAR for r in rows)):
            v.append("MEETS THE OWNER'S 90%")
        if enough and all(r[1]["fell"] and r[0]["fell"] >= 1.5 * r[1]["fell"] for r in rows):
            v.append("WARNS")
        if enough and all(r[0][20] - r[1][20] >= 1.5 for r in rows):
            v.append("LEANS UP")
        if enough and all(r[0][20] - r[1][20] <= -1.5 for r in rows):
            v.append("LEANS DOWN")
        verdicts[k] = ", ".join(v) or ("DESCRIBES ONLY" + ("" if enough else " (fewer than 10 episodes in a half)"))
        recent = [fdays[i] for i in eps if fdays[i] >= date(2025, 10, 1)]
        if recent:
            print("  since 2025-10: " + ", ".join(
                f"{d} ({paths[d][20]:+.1f}% in 20d)" if d in paths else f"{d} (not yet 20d)" for d in recent))
    print("\nVERDICTS")
    for k, v in verdicts.items():
        print(f"  {k:16} {v}")


if __name__ == "__main__":
    main()
