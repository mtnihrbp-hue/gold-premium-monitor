"""The order book and the big tickets on the sampled days (SP-D, 2026-10-05).

Data: research/data/tsetmc_intraday/{insCode}.json, the days with "trades" and "book" (every 8th
session, fetch_tsetmc_intraday.py): value traded by ticket size each minute, and the top-five
depth on each side each minute.

1. INSIDE THE SESSION (many minutes a day): the book's imbalance (bid depth - ask depth) / (both)
   at minute t against the fund's price move over the next 10 and 30 minutes, and against the
   move of the 10 minutes before (is the book only echoing the price?).
2. THE DAY: the share of the day's value done in big tickets (over 1B toman) and the closing hour's
   imbalance, against 18K's next 1 and 5 days -- descriptive only, about 90 days.
"""
import json
import os
import sys
from datetime import date

import numpy as np

from rd_rebuy import c, d

HERE = os.path.dirname(os.path.abspath(__file__))
INS = sys.argv[1] if len(sys.argv) > 1 else "34144395039913458"
F = json.load(open(os.path.join(HERE, "data", "tsetmc_intraday", f"{INS}.json"), encoding="utf-8"))
gix = {x: i for i, x in enumerate(d)}


def minutes(hhmm):
    return (hhmm // 100) * 60 + hhmm % 100


imb_all, fut10, fut30, past10, years = [], [], [], [], []
day_rows = []
for key, rec in sorted(F["days"].items()):
    if "book" not in rec or not rec.get("bars"):
        continue
    bars = {minutes(b[0]): b for b in rec["bars"]}
    book = {minutes(x[0]): x for x in rec["book"]}
    t_bars = sorted(bars)
    price_at = {}
    last = None
    for m in range(t_bars[0], t_bars[-1] + 1):
        if m in bars:
            last = bars[m][4]
        price_at[m] = last
    session = [m for m in sorted(book) if t_bars[0] + 10 <= m <= t_bars[-1] - 30]
    for m in session:
        bid, ask = book[m][1], book[m][2]
        if bid + ask <= 0 or m - 10 not in price_at or price_at.get(m) is None:
            continue
        imb_all.append((bid - ask) / (bid + ask))
        p0 = price_at[m]
        fut10.append((price_at[m + 10] / p0 - 1) * 100)
        fut30.append((price_at[m + 30] / p0 - 1) * 100)
        past10.append((p0 / price_at[m - 10] - 1) * 100 if price_at[m - 10] else np.nan)
        years.append(int(key[:4]))
    dt = date(int(key[:4]), int(key[4:6]), int(key[6:]))
    if "trades" in rec and dt in gix:
        tot = np.array([x[1:] for x in rec["trades"]]).sum(axis=0)
        big = tot[2:].sum() / tot.sum() if tot.sum() else np.nan
        last_hour = [book[m] for m in sorted(book) if m >= t_bars[-1] - 60]
        imb_close = np.mean([(x[1] - x[2]) / (x[1] + x[2]) for x in last_hour if x[1] + x[2] > 0]) if last_hour else np.nan
        i = gix[dt]
        nx1 = (c[i + 1] / c[i] - 1) * 100 if i + 1 < len(c) else np.nan
        nx5 = (c[i + 5] / c[i] - 1) * 100 if i + 5 < len(c) else np.nan
        day_rows.append((dt, big, imb_close, nx1, nx5))

imb_all, fut10, fut30, past10, years = map(np.array, (imb_all, fut10, fut30, past10, years))
print(f"{F['symbol']}: {len(set(r[0] for r in day_rows))} sampled sessions, {len(imb_all):,} book minutes")
print("\n1. INSIDE THE SESSION: the book's imbalance against the fund's price")
for y in sorted(set(years)) + [None]:
    sel = (years == y) if y else np.ones(len(years), bool)
    ok = sel & np.isfinite(past10)
    r10 = np.corrcoef(imb_all[ok], fut10[ok])[0, 1]
    r30 = np.corrcoef(imb_all[ok], fut30[ok])[0, 1]
    rp = np.corrcoef(imb_all[ok], past10[ok])[0, 1]
    hi, lo = imb_all[ok] > 0.5, imb_all[ok] < -0.5
    print(f"   {y or 'all years'}: {ok.sum():6,} minutes; with the next 10 min {r10:+.2f}, next 30 min {r30:+.2f}, the 10 before "
          f"{rp:+.2f};  bids far deeper (>0.5): next 30 min {np.mean(fut30[ok][hi]):+.3f}% ({hi.sum():,}), asks far deeper: "
          f"{np.mean(fut30[ok][lo]):+.3f}% ({lo.sum():,}), all {np.mean(fut30[ok]):+.3f}%")

print("\n2. THE DAY (descriptive): big tickets' share and the closing hour's imbalance against 18K's next days")
rows = np.array([r[1:] for r in day_rows], dtype=float)
ok = np.all(np.isfinite(rows), axis=1)
rows = rows[ok]
print(f"   {len(rows)} days; big tickets carried {np.median(rows[:, 0]) * 100:.0f}% of the value (median), range "
      f"{np.percentile(rows[:, 0], 10) * 100:.0f}-{np.percentile(rows[:, 0], 90) * 100:.0f}%")
for j, name in ((0, "big tickets' share"), (1, "closing hour's imbalance")):
    print(f"   {name:25} with 18K's next day {np.corrcoef(rows[:, j], rows[:, 2])[0, 1]:+.2f}, next 5 days "
          f"{np.corrcoef(rows[:, j], rows[:, 3])[0, 1]:+.2f}  (about {len(rows)} days: |r| under 0.2 is noise)")
