"""Fetch tgju's full daily history of 18K, the dollar and world gold for the SP-D research.

Writes research/data/tgju_history.json (not committed: it is data, and the runner stores
the same candles in market_daily_candles). Every research script here reads that file, so
the R&D reproduces without a database connection. SP_C_HANDOFF.md sections 46-47.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
import collector.tgju as tgju

tgju.REQUEST_TIMEOUT = (10, 60)
data = {}
for instrument in tgju.INSTRUMENTS:
    rows, start = [], 0
    while True:
        page = tgju.fetch_daily_candles(instrument, rows=1000, start=start, order="asc")
        rows += page
        start += len(page)
        if len(page) < 1000:
            break
    seen = set()
    data[instrument] = [r for r in rows if not (r["date"] in seen or seen.add(r["date"]))]
    print(instrument, len(data[instrument]), data[instrument][0]["date"], "..", data[instrument][-1]["date"])
os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
json.dump(data, open(os.path.join(HERE, "data", "tgju_history.json"), "w"))
