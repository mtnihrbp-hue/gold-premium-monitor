"""Tether over the Iranian weekend: does it tell Saturday's dollar and 18K? (SP-D, SP_D_HANDOFF.md section
42; the owner, 2026-10-16: "what are the signals to watch".)

tgju quotes Tether (crypto-tether-irr) every day, while the dollar and 18K close for the weekend: in 2025-26
the dollar had a Friday close on 27 of about 92 Fridays, and a Thursday close on 58. A move of Tether over
the weekend is known before Saturday's market opens. If Saturday follows it, the weekend's Tether is a
signal to watch, on a day the platforms reprice.

Rules, fixed before the run:
- Data: tgju's daily closes of Tether, the dollar (price_dollar_rl) and 18K (geram18), from Tether's
  first day (2020-11-12) to the latest close.
- A weekend: each Saturday S with a dollar close and an 18K close; L, the last day before S with both;
  F, the last day before S with a Tether close. Tether's weekend move: L to F. Saturday's moves: the
  dollar's and 18K's, L to S. Weekends with L more than 4 calendar days before S are left out.
- Every day, as a control for a lead in general: Tether's move on day t (the close before t to t)
  against the dollar's move from t to the next trading day.
- Reported: per half (2020-11 to 2023-06, 2023-07 to the end) and overall, the correlation of Tether's
  weekend move with Saturday's dollar and 18K, the share of weekends in the same direction, and the same
  on the weekends Tether moved 1% or more either way, with Saturday's mean move after them.
- Verdict, decided now: Tether's weekend move is A SIGNAL TO WATCH when, in both halves, its correlation
  with Saturday's dollar is at least 0.4 and, on weekends of a 1% move or more (at least 20 in each
  half), Saturday's dollar went the same way at least 65% of the time. Otherwise NOT SHOWN.

Run: python research/rd_tether_lead.py   (reads tgju from the workstation directly)
"""

import os
import sys
from datetime import date, timedelta

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rd_news_events import series  # noqa: E402

HALVES = (("2020-11 to 2023-06", date(2020, 11, 12), date(2023, 6, 30)), ("2023-07 to the end", date(2023, 7, 1), date(2100, 1, 1)))
BIG = 0.01


def last_before(days_sorted, day):
    import bisect
    k = bisect.bisect_left(days_sorted, day) - 1
    return days_sorted[k] if k >= 0 else None


def main():
    usdt, usd, gold = series("crypto-tether-irr"), series("price_dollar_rl"), series("geram18")
    t_days, both = sorted(usdt), sorted(set(usd) & set(gold))
    first = t_days[0]
    rows = []
    for s in both:
        if s < first or s.weekday() != 5:          # Saturday
            continue
        last = last_before(both, s)
        fri = last_before(t_days, s)
        if not last or not fri or (s - last).days > 4 or fri <= last:
            continue
        tether = usdt[fri] / usdt[last] - 1
        rows.append((s, tether, usd[s] / usd[last] - 1, gold[s] / gold[last] - 1))
    print(f"{len(rows)} weekends with Tether moving over them, {rows[0][0]} .. {rows[-1][0]}")
    verdict = []
    for label, lo, hi in HALVES + (("overall", date(2000, 1, 1), date(2100, 1, 1)),):
        r = [x for x in rows if lo <= x[0] <= hi]
        if len(r) < 10:
            continue
        t = np.array([x[1] for x in r])
        du, dg = np.array([x[2] for x in r]), np.array([x[3] for x in r])
        corr_u, corr_g = np.corrcoef(t, du)[0, 1], np.corrcoef(t, dg)[0, 1]
        same_u = np.mean(np.sign(t) == np.sign(du))
        big = np.abs(t) >= BIG
        same_big = np.mean(np.sign(t[big]) == np.sign(du[big])) if big.any() else np.nan
        up, down = t >= BIG, t <= -BIG
        print(f"\n  {label}: {len(r)} weekends; Tether's weekend move against Saturday's: dollar r = {corr_u:+.2f}, "
              f"18K r = {corr_g:+.2f}; the dollar the same way {same_u:.0%}")
        print(f"    weekends of 1%+ ({big.sum()}): the dollar the same way {same_big:.0%}; 18K the same way "
              f"{np.mean(np.sign(t[big]) == np.sign(dg[big])) if big.any() else np.nan:.0%}")
        if up.any():
            print(f"    Tether up 1%+ ({up.sum()}): Saturday's dollar {du[up].mean() * 100:+.2f}%, 18K {dg[up].mean() * 100:+.2f}%")
        if down.any():
            print(f"    Tether down 1%+ ({down.sum()}): Saturday's dollar {du[down].mean() * 100:+.2f}%, 18K {dg[down].mean() * 100:+.2f}%")
        print(f"    every Saturday: the dollar {du.mean() * 100:+.2f}%, 18K {dg.mean() * 100:+.2f}%")
        if label != "overall":
            verdict.append(corr_u >= 0.4 and big.sum() >= 20 and same_big >= 0.65)

    # every day: Tether today against the dollar tomorrow
    u_days = sorted(usd)
    lead = []
    for k in range(1, len(u_days) - 1):
        d0, d1, d2 = u_days[k - 1], u_days[k], u_days[k + 1]
        if d1 < first or (d2 - d1).days > 4:
            continue
        t0, t1 = last_before(t_days, d1 + timedelta(days=1)), last_before(t_days, d1)
        if not t0 or not t1 or t0 != d1:
            continue
        lead.append((usdt[t0] / usdt[t1] - 1, usd[d2] / usd[d1] - 1, usd[d1] / usd[d0] - 1))
    if lead:
        a = np.array(lead)
        print(f"\n  every trading day ({len(a)}): Tether today against the dollar's next day r = {np.corrcoef(a[:, 0], a[:, 1])[0, 1]:+.2f}; "
              f"the dollar's own day against its next r = {np.corrcoef(a[:, 2], a[:, 1])[0, 1]:+.2f}")
    print(f"\nverdict (decided before the run): {'A SIGNAL TO WATCH' if len(verdict) == 2 and all(verdict) else 'NOT SHOWN'}")


if __name__ == "__main__":
    main()
