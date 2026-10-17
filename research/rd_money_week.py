"""The gold funds' money as "x times the usual": its normal range, and what followed the unusual weeks
(SP-D, SP_D_HANDOFF.md section 46; the owner, 2026-10-17: "Money in: x times of average last 7D, in a
normal range. so we need some statsticall analysis as well").

Rules, fixed before the run:
- Data: the 18 gold funds' daily individual trading (src/seed/gold_fund_daily.json, 2017-07-30 to
  2026-10-03: buy value, buyers, sell value, sellers, in rial); tgju's daily 18K closes (live,
  research/rd_news_events.series).
- Net money of a fund day: individuals' buy value minus their sell value, summed over the funds.
- Reading W, the week (proposed): the net money of the last 7 fund days, as a multiple of the usual week,
  7 times the mean daily net of the 250 fund days before those 7. Undefined when that mean is 0 or less.
- Reading D, the day (the owner's words read literally): the latest day's net, as a multiple of the mean
  daily net of the 7 days before it. Undefined when that mean is 0 or less. Described only: how often it
  is undefined, and how far it swings.
- W's state: its rank against its own previous 250 values (at least 100): HIGH at 90% or more, LOW under
  10%, NORMAL between (gold_demand.UNUSUAL). The normal range in the reader's terms: the multiples at the
  10th and 90th percentile of the 250 values to the latest day.
- Agreement: the share of days on which W's state equals gold_demand's money state (the net share of the
  7 days' buying and selling, ranked the same way), which Direction's GOLD DEMAND shows today.
- Outcome, from the 18K close of the fund day (or the last tgju close before it): the return over the next
  20 tgju trading days, and a fall of 5% or more within them (the lowest close of t+1..t+20 at least 5%
  under t's), as research/rd_falls.py.
- Episodes: a state's episode starts on its first day in it, 10 fund days or more after its last start.
- Halves: the days with a state, split at their middle day.
- Reported per half: each state's episodes, mean 20-day return and 5%-fall rate, against every day's
  with a state in that half; W's quintiles (by rank), every day, as a check of separation across the
  range; the episodes since 2024-10 one by one (the precedents).
- Verdicts, decided now:
    WARNS          a state's 5%-fall rate is at least 1.5 times every day's in both halves, with at least
                   10 episodes in each
    LEANS UP/DOWN  its mean 20-day return is at least 1.5 points above / below every day's in both halves,
                   with at least 10 episodes in each
    DESCRIBES ONLY otherwise: the reading says where the week stands, not what comes next

Run: python research/rd_money_week.py   (reads tgju from the workstation directly)
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

WEEK, YEAR, MIN_RANK, UNUSUAL = 7, 250, 100, 10
AHEAD, FALL, GAP = 20, -0.05, 10


def rank_of(history, value):
    h = np.asarray([x for x in history if np.isfinite(x)])
    return float(np.mean(h < value) * 100) if len(h) >= MIN_RANK and np.isfinite(value) else np.nan


def state_of(rank):
    if not np.isfinite(rank):
        return None
    return "HIGH" if rank >= 100 - UNUSUAL else "LOW" if rank < UNUSUAL else "NORMAL"


def load_funds():
    seed = json.load(open(os.path.join(HERE, "..", "src", "seed", "gold_fund_daily.json"), encoding="utf-8"))
    days = sorted(date.fromisoformat(k) for k in seed["days"])
    a = np.array([seed["days"][d.isoformat()][:4] for d in days], dtype=float)
    return days, a


def readings(a):
    n = len(a)
    net = a[:, 0] - a[:, 2]
    w = np.full(n, np.nan)
    dd = np.full(n, np.nan)
    share = np.full(n, np.nan)
    for i in range(n):
        if i >= WEEK + YEAR - 1:
            usual = net[i - WEEK - YEAR + 1:i - WEEK + 1].mean() * WEEK
            if usual > 0:
                w[i] = net[i - WEEK + 1:i + 1].sum() / usual
        if i >= WEEK:
            m = net[i - WEEK:i].mean()
            if m > 0:
                dd[i] = net[i] / m
        if i >= WEEK - 1:
            bv, sv = a[i - WEEK + 1:i + 1, 0].sum(), a[i - WEEK + 1:i + 1, 2].sum()
            share[i] = (bv - sv) / (bv + sv) if bv + sv else np.nan
    w_rank = np.array([rank_of(w[max(0, i - YEAR):i], w[i]) for i in range(n)])
    s_rank = np.array([rank_of(share[max(0, i - YEAR):i], share[i]) for i in range(n)])
    return net, w, dd, w_rank, s_rank


def outcomes(fdays):
    gold = series("geram18")
    gdays = sorted(gold)
    close = np.array([gold[d] for d in gdays])
    ret, fell = {}, {}
    for d in fdays:
        k = bisect_right(gdays, d) - 1
        if k < 0 or (d - gdays[k]).days > 7 or k + AHEAD >= len(gdays):
            continue
        ret[d] = (close[k + AHEAD] / close[k] - 1) * 100
        fell[d] = float(close[k + 1:k + AHEAD + 1].min() / close[k] - 1 <= FALL)
    return ret, fell


def episodes(days, states, want):
    out, last = [], -10 ** 9
    for i, d in enumerate(days):
        if states[i] == want and (i == 0 or states[i - 1] != want) and i - last >= GAP:
            out.append(i)
            last = i
    return out


def main():
    fdays, a = load_funds()
    net, w, dd, w_rank, s_rank = readings(a)
    w_state = [state_of(r) for r in w_rank]
    s_state = [state_of(r) for r in s_rank]
    ret, fell = outcomes(fdays)

    print("READING D (the latest day against the 7 days before it)")
    d_ok = np.isfinite(dd[WEEK:])
    print(f"  defined on {d_ok.mean():.0%} of {len(d_ok)} fund days; undefined when the 7 days before were net out "
          f"or flat")
    finite = dd[np.isfinite(dd)]
    print(f"  where defined, 10th / 50th / 90th percentile: {np.percentile(finite, 10):+.1f} / "
          f"{np.percentile(finite, 50):+.1f} / {np.percentile(finite, 90):+.1f} times")

    have = [i for i in range(len(fdays)) if w_state[i] is not None]
    print(f"\nREADING W (7 days against the usual week): a state on {len(have)} fund days, "
          f"{fdays[have[0]]} to {fdays[have[-1]]}")
    both = [i for i in have if s_state[i] is not None]
    agree = np.mean([w_state[i] == s_state[i] for i in both])
    print(f"  agrees with gold_demand's money state on {agree:.0%} of {len(both)} days")
    for st in ("HIGH", "NORMAL", "LOW"):
        print(f"  {st:6} {np.mean([w_state[i] == st for i in have]):.0%} of days")
    last = len(fdays) - 1
    window = w[max(0, last - YEAR + 1):last + 1]
    window = window[np.isfinite(window)]
    print(f"  the normal range to {fdays[last]}: {np.percentile(window, 10):+.1f} to {np.percentile(window, 90):+.1f} "
          f"times the usual week")
    usual = net[last - WEEK - YEAR + 1:last - WEEK + 1].mean() * WEEK / 1e10
    print(f"  the latest: {net[last - WEEK + 1:last + 1].sum() / 1e10:,.0f}B toman in 7 days, usual week "
          f"{usual:,.0f}B, W {w[last]:+.1f} times, rank {w_rank[last]:.0f}%, {w_state[last]}")

    mid = have[len(have) // 2]
    halves = (("first half", have[0], mid), ("second half", mid, have[-1] + 1))
    print(f"\nWHAT FOLLOWED (18K over the next 20 tgju days; halves split at {fdays[mid]})")
    verdict = {}
    for st in ("HIGH", "LOW"):
        eps = episodes(fdays, w_state, st)
        row = []
        for name, lo, hi in halves:
            base = [fdays[i] for i in range(lo, hi) if w_state[i] is not None and fdays[i] in ret]
            ep = [fdays[i] for i in eps if lo <= i < hi and fdays[i] in ret]
            b_ret, b_fall = np.mean([ret[d] for d in base]), np.mean([fell[d] for d in base])
            e_ret = np.mean([ret[d] for d in ep]) if ep else np.nan
            e_fall = np.mean([fell[d] for d in ep]) if ep else np.nan
            print(f"  {st:4} {name:11} {len(ep):3} episodes: 20-day {e_ret:+.2f}% (every day {b_ret:+.2f}%), "
                  f"5% fall {e_fall:.0%} (every day {b_fall:.0%})")
            row.append((len(ep), e_ret - b_ret, e_fall / b_fall if b_fall else np.nan))
        enough = all(n >= 10 for n, _, _ in row)
        if enough and all(r >= 1.5 for _, _, r in row):
            verdict[st] = "WARNS"
        elif enough and all(x >= 1.5 for _, x, _ in row):
            verdict[st] = "LEANS UP"
        elif enough and all(x <= -1.5 for _, x, _ in row):
            verdict[st] = "LEANS DOWN"
        else:
            verdict[st] = "DESCRIBES ONLY" + ("" if enough else " (fewer than 10 episodes in a half)")

    print("\nW'S QUINTILES (every day with a rank)")
    for name, lo, hi in halves:
        cells = []
        for q in range(5):
            idx = [fdays[i] for i in range(lo, hi) if np.isfinite(w_rank[i]) and q * 20 <= w_rank[i] < (q + 1) * 20 + (q == 4)
                   and fdays[i] in ret]
            cells.append(f"{np.mean([ret[d] for d in idx]):+.1f}% / {np.mean([fell[d] for d in idx]):.0%}")
        print(f"  {name:11} " + " | ".join(cells))

    print("\nTHE PRECEDENTS SINCE 2024-10 (episode start, W, 18K's next 20 days, a 5% fall within them)")
    for st in ("HIGH", "LOW"):
        for i in episodes(fdays, w_state, st):
            if fdays[i] >= date(2024, 10, 1):
                d = fdays[i]
                after = f"{ret[d]:+.1f}%, {'fell 5%' if fell[d] else 'no 5% fall'}" if d in ret else "not yet 20 days"
                print(f"  {st:4} {d}  {w[i]:+.1f} times  {after}")

    print("\nVERDICTS")
    for st, v in verdict.items():
        print(f"  {st:4} {v}")


if __name__ == "__main__":
    main()
