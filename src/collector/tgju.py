"""tgju.org daily candles: open, low, high, close for 18K gold and the dollar.

SP-D technical-analysis track, step 1 (SP_C_HANDOFF.md section 41). Our own candles
are too short a history for technical analysis, and platform_candles are single points.
tgju's history pages publish real daily candles back to 2013, and its daily 18K close
tracks our platforms at 0.95 daily correlation, a median +0.19% apart.

This is a separate instrument with its own provenance. It is never mixed with
platform prices: FACTS keep their source.

The endpoint is the one tgju's own public history page reads. A run requests only the
rows it lacks: while history is missing, one page of it, oldest first, from where the
stored history ends; after that a short window of the newest days. The whole history in
one request was tried first and failed from the runner at 14:00 on 2026-09-30: tgju's
answer time follows its load, not only the size (section 43). Each fetch runs on a
daemon thread under one shared deadline, the pattern collector/iran.py uses since
SP-C.9, so a hung request can never hold a run. This module collects only; main stores
(section 41.6).
"""

import re
import threading
import time

import requests

API = "https://api.tgju.org/v1/market/indicator/summary-table-data/{instrument}"

SOURCE = "tgju"
UNIT = "IRR"

# tgju's instrument key -> the name this system stores it under.
INSTRUMENTS = {
    "geram18": "TGJU_GOLD_18K",
    "price_dollar_rl": "TGJU_USD_IRR",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/138.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

# A 1,000-row page took 1-5 s from abroad on 2026-09-30, and 3 rows took 6.7 s when
# tgju was busy. The read timeout leaves room for a busy moment; the deadline bounds
# the run's cost at 30 s whatever happens.
REQUEST_TIMEOUT = (5, 20)
DEADLINE_SECONDS = 30


def _number(cell):
    """A price cell such as '252,655,000' (sometimes wrapped in markup), as a float."""
    digits = re.sub(r"[^\d.]", "", re.sub(r"<[^>]+>", "", str(cell)))
    if not digits:
        raise ValueError(f"no number in {cell!r}")
    return float(digits)


def _text(cell):
    return re.sub(r"<[^>]+>", "", str(cell)).strip()


def parse_rows(payload):
    """tgju rows -> [{date, jdate, open, low, high, close}], newest first, in Rial.

    Row layout, as the history page labels its columns: open, low, high, close,
    change, change %, Gregorian date (YYYY/MM/DD), Persian date.
    """
    candles = []
    for row in payload.get("data") or []:
        candles.append({
            "date": _text(row[6]).replace("/", "-"),
            "jdate": _text(row[7]),
            "open": _number(row[0]),
            "low": _number(row[1]),
            "high": _number(row[2]),
            "close": _number(row[3]),
        })
    return candles


def fetch_daily_candles(instrument, rows=5, start=0, order="desc"):
    """`rows` daily candles for one tgju instrument, from offset `start` in `order`:
    "desc" is newest first, "asc" oldest first. Raises on failure."""
    response = requests.get(
        API.format(instrument=instrument),
        params={"lang": "fa", "order_dir": order, "start": start, "length": rows},
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    candles = parse_rows(response.json())
    if not candles:
        raise ValueError("no rows returned")
    return candles


def collect_daily_candles(rows=5):
    """{instrument: {"status": "OK", "candles": [...]}} or {"status": "ERROR: ..."}.

    `rows` is one count for every instrument (newest first), or {instrument: count},
    or {instrument: (start, count, order)}, so an instrument still paging through its
    history does not make the others fetch theirs.
    Instruments are isolated from each other, and all of them together are bounded by
    DEADLINE_SECONDS: a fetch still running at the deadline is abandoned and reported
    as a timeout rather than awaited.
    """
    results = {name: {"status": "TIMEOUT"} for name in INSTRUMENTS}
    requested = rows if isinstance(rows, dict) else {name: rows for name in INSTRUMENTS}
    plans = {name: (value if isinstance(value, tuple) else (0, value, "desc"))
             for name, value in requested.items()}

    def runner(instrument):
        start, count, order = plans[instrument]
        try:
            results[instrument] = {"status": "OK", "candles": fetch_daily_candles(
                instrument, count, start=start, order=order)}
        except Exception as e:
            results[instrument] = {"status": f"ERROR: {e}"}

    threads = [threading.Thread(target=runner, args=(name,), daemon=True) for name in INSTRUMENTS]
    for thread in threads:
        thread.start()
    deadline = time.monotonic() + DEADLINE_SECONDS
    for thread in threads:
        thread.join(timeout=max(0.0, deadline - time.monotonic()))
    return {name: dict(result) for name, result in results.items()}
