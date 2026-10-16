"""Falls, and parking in fixed income: which signals came before 18K's falls, and did leaving on them pay?
(SP-D, SP_D_HANDOFF.md section 41; the owner, 2026-10-16: "the whole benefit of the system should be ...
to collect data, analyze and predict such falls. or even when the whole market is on wait move to fixed
income. so it should be able to see if the rally is coming to an end, how long park, what are the
signals to watch. how can the gold etf money flow help.")

40.1 asked a buyer's question (convert within a month: no rule beat buying at once). This asks a
holder's: when to step out of gold into fixed income, and for how long.

Rules, fixed before the run:
- Data: tgju's daily 18K and dollar to the latest close (live, research/rd_news_events.series); the 18
  gold funds' daily individual trading (src/seed/gold_fund_daily.json, from 2017-07); the fixed-income
  fund's level (src/seed/fixed_income.json, from 2015-03).
- The outcome, for day t: a fall of 5% or more within the next 20 trading days (the lowest close of
  t+1..t+20 at least 5% below t's close; "usually 19%" in Direction), and the 20-day return.
- Signals, each on or off at day t's close:
    18K under its 50-day                    18K under 50-day; EMA20 under EMA50
    the dollar under its 50-day
    18K stretched                           15% or more above its 50-day
    a dollar spike                          the dollar up 8% or more in 10 trading days
    sideways                                the room's market-state rule: the 60-day efficiency ratio under
                                            a random walk's (room.efficiency_sideways) and no new 60-day
                                            closing high in the last 20 days
    turbulence                              18K's 20-day volatility in the top 20% of its past year, or 18K
                                            10% or more under its year's high (37.6)
    a rush of buyers                        the funds' buyers per day over 7 days against the 120 before,
                                            in the top 10% of its past year (gold_demand's "people HIGH")
    heavy money out                         the funds' net individual money over 7 days in the bottom 10%
    a rush in turbulence                    both
- Counted by episodes: a signal's episode starts on its first day on, 10 trading days or more after its
  last start.
- Reported per signal and era (2014-2019, 2020-2026; the funds' signals from 2018):
    the share of episodes followed by a 5% fall within 20 days, against every day's;
    the mean 20-day return after, against every day's;
    PARKING: from each episode's start, the rial in fixed income for 20 trading days, then back to gold:
    the fund's growth over 18K's over those days, minus 1 (above 0, parking paid);
    recall: of the falls (a fall's start is its first day of a coming 5% fall, 20 days after the last),
    the share with the signal on that day or within the 5 before.
- Verdicts, decided now:
    WARNS        the 5%-fall rate after its episodes is at least 1.5 times every day's, in both eras,
                 with at least 10 episodes in each
    PARKING PAYS its parking gain's mean is above 0 in both eras, and positive in at least 55% of its
                 episodes overall
  The funds' signals have one era (2018-2026) and are judged on it, marked as such.

Run: python research/rd_falls.py   (reads tgju from the workstation directly)
"""

import json
import os
import sys
from bisect import bisect_right
from datetime import date
from statistics import mean

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "src"))
from rd_news_events import series  # noqa: E402

AHEAD = 20
FALL = -0.05
GAP = 10
ERAS = (("2014-2019", date(2014, 1, 1), date(2019, 12, 31)), ("2020-2026", date(2020, 1, 1), date(2026, 12, 31)))


def ema(x, n):
    out, k = np.empty(len(x)), 2 / (n + 1)
    out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = x[i] * k + out[i - 1] * (1 - k)
    return out


def rank_against_past(x, window=250, min_n=100):
    out = np.full(len(x), np.nan)
    for i in range(len(x)):
        h = x[max(0, i - window):i]
        h = h[np.isfinite(h)]
        if len(h) >= min_n and np.isfinite(x[i]):
            out[i] = np.mean(h < x[i])
    return out


def load():
    from analysis.room import efficiency_sideways
    gold, usd = series("geram18"), series("price_dollar_rl")
    days = [d for d in sorted(gold) if d.year >= 2013]
    usd_days = sorted(usd)
    close = np.array([gold[d] for d in days])
    dollar = np.array([usd[usd_days[max(0, bisect_right(usd_days, d) - 1)]] for d in days])
    n = len(days)
    sma50 = np.array([close[max(0, i - 49):i + 1].mean() if i >= 49 else np.nan for i in range(n)])
    usd50 = np.array([dollar[max(0, i - 49):i + 1].mean() if i >= 49 else np.nan for i in range(n)])
    e20, e50 = ema(close, 20), ema(close, 50)
    rets = np.concatenate([[np.nan], np.diff(np.log(close))])
    vol20 = np.array([np.std(rets[i - 19:i + 1]) if i >= 20 else np.nan for i in range(n)])
    high250 = np.array([close[max(0, i - 249):i + 1].max() for i in range(n)])
    high60 = np.array([close[max(0, i - 59):i + 1].max() for i in range(n)])
    side = efficiency_sideways(close, np.zeros(n))
    new_high_20 = np.array([i >= 80 and close[i - 19:i + 1].max() >= high60[i - 20] for i in range(n)])
    vol_rank = rank_against_past(vol20)
    sig = {
        "18K under its 50-day": close < sma50,
        "EMA20 under EMA50": e20 < e50,
        "the dollar under its 50-day": dollar < usd50,
        "18K stretched 15%+": close >= sma50 * 1.15,
        "a dollar spike (+8% in 10d)": np.array([i >= 10 and dollar[i] / dollar[i - 10] - 1 >= 0.08 for i in range(n)]),
        "sideways": side & ~new_high_20,
        "turbulence": (vol_rank >= 0.8) | (close <= high250 * 0.90),
    }
    # the gold funds: 7-day buyers against the 120 days before, and 7-day net money
    seed = json.load(open(os.path.join(HERE, "..", "src", "seed", "gold_fund_daily.json"), encoding="utf-8"))
    fdays = sorted(date.fromisoformat(k) for k in seed["days"])
    a = np.array([seed["days"][d.isoformat()][:4] for d in fdays], dtype=float)
    people, money = np.full(len(a), np.nan), np.full(len(a), np.nan)
    for i in range(127, len(a)):
        bv, bc, sv, sc = a[i - 6:i + 1].sum(axis=0)
        prior = a[i - 126:i - 6, 1].mean()
        people[i] = (bc / 7) / prior if prior > 0 else np.nan
        money[i] = (bv - sv) / (bv + sv) if bv + sv else np.nan
    p_rank, m_rank = rank_against_past(people), rank_against_past(money)
    on_day = {d: (p_rank[k], m_rank[k]) for k, d in enumerate(fdays)}
    rush = np.zeros(n, dtype=bool)
    out = np.zeros(n, dtype=bool)
    funds_known = np.zeros(n, dtype=bool)
    for i, d in enumerate(days):
        j = bisect_right(fdays, d) - 1
        if j >= 0 and (d - fdays[j]).days <= 7 and np.isfinite(p_rank[j]):
            funds_known[i] = True
            rush[i] = p_rank[j] >= 0.9
            out[i] = np.isfinite(m_rank[j]) and m_rank[j] < 0.1
    sig["a rush of buyers (funds)"] = rush
    sig["heavy money out (funds)"] = out
    sig["a rush in turbulence (funds)"] = rush & sig["turbulence"]
    fi = json.load(open(os.path.join(HERE, "..", "src", "seed", "fixed_income.json"), encoding="utf-8"))["level"]
    fi_days = sorted(date.fromisoformat(k) for k in fi)
    level = np.array([fi[fi_days[bisect_right(fi_days, d) - 1].isoformat()] if bisect_right(fi_days, d) > 0 else np.nan
                      for d in days], dtype=float)
    return days, close, level, sig, funds_known


def main():
    days, close, level, sig, funds_known = load()
    n = len(days)
    fell = np.full(n, np.nan)
    ret20 = np.full(n, np.nan)
    for i in range(n - AHEAD):
        fell[i] = float(close[i + 1:i + AHEAD + 1].min() / close[i] - 1 <= FALL)
        ret20[i] = close[i + AHEAD] / close[i] - 1
    print(f"{n} days {days[0]} .. {days[-1]}")
    fall_starts, last = [], -10**9
    for i in range(n):
        if fell[i] == 1 and i - last >= AHEAD:
            fall_starts.append(i)
            last = i
    print(f"falls of 5%+ within 20 days: {len(fall_starts)} starts since {days[0].year} "
          f"(every day's rate: {np.nanmean(fell):.0%})")
    verdicts = {}
    for name, on in sig.items():
        funds = "(funds)" in name
        starts, last = [], -10**9
        for i in range(1, n - AHEAD):
            if on[i] and not on[i - 1] and i - last >= GAP and (not funds or funds_known[i]):
                starts.append(i)
                last = i
        print(f"\n{name}")
        warns, pays = [], []
        all_gain = []
        for era, lo, hi in ERAS:
            idx = [i for i in starts if lo <= days[i] <= hi]
            base_idx = [i for i in range(n - AHEAD) if lo <= days[i] <= hi and (not funds or funds_known[i])]
            if not idx or not base_idx:
                print(f"  {era}: no episodes")
                continue
            rate = np.mean([fell[i] for i in idx])
            base = np.nanmean([fell[i] for i in base_idx])
            r_after = np.mean([ret20[i] for i in idx]) * 100
            r_base = np.nanmean([ret20[i] for i in base_idx]) * 100
            gains = [((level[i + AHEAD] / level[i]) / (close[i + AHEAD] / close[i]) - 1) * 100
                     for i in idx if np.isfinite(level[i]) and np.isfinite(level[i + AHEAD])]
            all_gain += gains
            fs = [s for s in fall_starts if lo <= days[s] <= hi and (not funds or funds_known[s])]
            recall = (np.mean([any(on[max(0, s - 5):s + 1]) for s in fs]) if fs else float("nan"))
            gain_txt = f"parking {mean(gains):+.2f}% (paid {np.mean([g > 0 for g in gains]):.0%})" if gains else "parking n/a"
            print(f"  {era}: {len(idx):>3} episodes; a 5% fall after {rate:.0%} (every day {base:.0%}, x{rate / base:.1f}); "
                  f"20d return {r_after:+.1f}% ({r_base:+.1f}%); {gain_txt}; caught {recall:.0%} of {len(fs)} falls")
            warns.append(len(idx) >= 10 and rate >= 1.5 * base)
            pays.append(bool(gains) and mean(gains) > 0)
        if funds:
            w = "WARNS (one era)" if warns and any(warns) else "does not warn"
            p = "PARKING PAYS (one era)" if pays and any(pays) and all_gain and np.mean([g > 0 for g in all_gain]) >= 0.55 else "parking does not pay"
        else:
            w = "WARNS" if len(warns) == 2 and all(warns) else "does not warn"
            p = "PARKING PAYS" if len(pays) == 2 and all(pays) and all_gain and np.mean([g > 0 for g in all_gain]) >= 0.55 else "parking does not pay"
        verdicts[name] = f"{w}; {p}"
    print("\nverdicts (decided before the run):")
    for name, v in verdicts.items():
        print(f"  {name:<34} {v}")


if __name__ == "__main__":
    main()
