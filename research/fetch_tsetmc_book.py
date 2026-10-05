"""The gold fund's order book on every session, condensed to its closing hour (SP-D, 2026-10-05).

rd_fund_book.py found, on 65 sampled days, the closing hour's book imbalance correlating +0.34 with
18K's next five days. This fetches BestLimits/{ins}/{day} for every session of 2023-10 -> 2026-10
and keeps, per day: the closing hour's mean imbalance (bid - ask depth over both, top five), the
whole session's, the last minute's, and the mean spread. Writes
research/data/tsetmc_intraday/{ins}_book_daily.json (git-ignored). Resumable.
"""
import json
import os
import sys
import time

from fetch_tsetmc_intraday import OUT, book_summary, fund_days, get

INS = sys.argv[1] if len(sys.argv) > 1 else "34144395039913458"
path = os.path.join(OUT, f"{INS}_book_daily.json")
data = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
days = fund_days(INS)
t0 = time.time()
print(f"{len(days)} sessions, {len(data)} already", flush=True)
for n, day in enumerate(days):
    if str(day) in data:
        continue
    j = get(f"BestLimits/{INS}/{day}", timeout=180)
    rows = book_summary(j.get("bestLimitsHistory", [])) if j else []
    rec = {}
    if rows:
        mins = [(r[0] // 100) * 60 + r[0] % 100 for r in rows]
        end = mins[-1]
        imb = [(r[1] - r[2]) / (r[1] + r[2]) for r in rows if r[1] + r[2] > 0]
        close_hour = [(r[1] - r[2]) / (r[1] + r[2]) for r, m in zip(rows, mins) if m >= end - 60 and r[1] + r[2] > 0]
        spread = [(r[4] / r[3] - 1) * 100 for r in rows if r[3] > 0 and r[4] > 0]
        rec = {"close_hour": sum(close_hour) / len(close_hour) if close_hour else None,
               "session": sum(imb) / len(imb) if imb else None,
               "last": imb[-1] if imb else None, "spread": sum(spread) / len(spread) if spread else None,
               "minutes": len(rows)}
    data[str(day)] = rec
    if len(data) % 25 == 0:
        json.dump(data, open(path, "w", encoding="utf-8"))
        print(f"  {day}: {len(data)}/{len(days)}  {time.time() - t0:.0f}s", flush=True)
    time.sleep(0.6)
json.dump(data, open(path, "w", encoding="utf-8"))
print(f"done: {len(data)} sessions in {time.time() - t0:.0f}s", flush=True)
