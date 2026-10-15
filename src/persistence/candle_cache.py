"""The daily candles, kept between runs (SP-D, SP_D_HANDOFF.md section 34).

Neon's free plan allows 5 GB of outbound transfer a month. Every scheduled run read tgju's daily
candles in full -- 18K up to three times, the dollar, world gold's 12,000 days -- about 26,000 rows a
run for history that only ever grows by one day. The candles are stored first-seen and never
revised (repository.save_daily_candles), so a copy kept between runs stays right: each read asks
only for the instrument's count and latest day, and fetches the days after the copy's when there
are new ones. A copy that disagrees in any other way is dropped and the instrument read in full.

On when CANDLE_CACHE_FILE names the file -- the workflow sets it and keeps the file in its cache
beside state.json. Unset (tests, local runs), every read goes to the database as before.

`direct()` is the route when the database cannot be read at all (section 35.2): tgju's own recent
candles, fetched in one request. It is for readers that draw the recent chart, never for those
that replay the whole history (the room, the quant engine), which would silently read less.
"""

import json
import os
from datetime import date

FIELDS = ("trade_date", "open", "high", "low", "close", "source_quality")

# One tgju request. On 18K's history to 2026-10-14 the 21:00 chart drawn from the last 400 days
# or more -- its EMAs, swing levels, trendlines, Fibonacci and the chartist's reading -- is the one
# drawn from all 3,529 (EMA50 within 5e-7 at 400, exact at 1,000); 1,000 takes about a second.
DIRECT_ROWS = 1000


class Candle:
    """One stored candle with the attributes the readers use."""
    __slots__ = FIELDS

    def __init__(self, trade_date, open_, high, low, close, source_quality):
        self.trade_date, self.open, self.high, self.low, self.close = trade_date, open_, high, low, close
        self.source_quality = source_quality


def _path():
    return os.environ.get("CANDLE_CACHE_FILE") or None


def _load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save(path, cache):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cache, f, separators=(",", ":"))
    except OSError as e:
        print(f"Candle cache not saved: {e}")


def _query(session, source, instrument, after=None):
    from database.models import MarketDailyCandle as M
    q = (session.query(M.trade_date, M.open, M.high, M.low, M.close, M.source_quality)
         .filter(M.source == source, M.instrument == instrument))
    if after is not None:
        q = q.filter(M.trade_date > after)
    return [[r[0].isoformat(), float(r[1]), float(r[2]), float(r[3]), float(r[4]), r[5]]
            for r in q.order_by(M.trade_date.asc()).all()]


def candles(session, source, instrument):
    """The instrument's stored candles, oldest first, as Candle objects."""
    path = _path()
    if path is None:
        rows = _query(session, source, instrument)
    else:
        from sqlalchemy import func
        from database.models import MarketDailyCandle as M
        count, latest = (session.query(func.count(M.id), func.max(M.trade_date))
                         .filter(M.source == source, M.instrument == instrument).one())
        cache = _load(path)
        key = f"{source}|{instrument}"
        kept = cache.get(key) or []
        if kept and len(kept) == count and latest is not None and kept[-1][0] == latest.isoformat():
            rows = kept
        else:
            rows = None
            if kept and latest is not None and kept[-1][0] < latest.isoformat():
                new = _query(session, source, instrument, after=date.fromisoformat(kept[-1][0]))
                if len(kept) + len(new) == count:
                    rows = kept + new
            if rows is None:
                rows = _query(session, source, instrument)
            cache[key] = rows
            _save(path, cache)
    return [Candle(date.fromisoformat(r[0]), r[1], r[2], r[3], r[4], r[5]) for r in rows]


def full_history(instrument, today):
    """tgju's whole history of a stored instrument name, fetched from tgju itself (1,000 rows a
    request, oldest first), classified and filtered as `direct()`: the same days the database holds,
    for readers that rank against all of them (/Direction while the database is out of reach, SP-D
    section 35.8). Raises when tgju cannot be read."""
    from collector.tgju import INSTRUMENTS, fetch_daily_candles
    from validation.data import classify_daily_candle
    key = next(k for k, name in INSTRUMENTS.items() if name == instrument)
    seen, start = {}, 0
    while True:
        page = fetch_daily_candles(key, DIRECT_ROWS, start=start, order="asc")
        for c in page:
            trade_date = date.fromisoformat(c["date"])
            quality = classify_daily_candle(c)
            if trade_date >= today or quality == "INVALID" or trade_date in seen:
                continue
            seen[trade_date] = Candle(trade_date, c["open"], c["high"], c["low"], c["close"], quality)
        if len(page) < DIRECT_ROWS:
            break
        start += DIRECT_ROWS
    return [seen[d] for d in sorted(seen)]


def direct(instrument, today, rows=DIRECT_ROWS):
    """tgju's completed candles for a stored instrument name, fetched from tgju itself, oldest
    first, classified as main stores them: today's incomplete candle and rows without a valid
    price are dropped. Raises when tgju cannot be read."""
    from collector.tgju import INSTRUMENTS, fetch_daily_candles
    from validation.data import classify_daily_candle
    key = next(k for k, name in INSTRUMENTS.items() if name == instrument)
    seen = {}
    for c in fetch_daily_candles(key, rows, order="desc"):
        trade_date = date.fromisoformat(c["date"])
        quality = classify_daily_candle(c)
        if trade_date >= today or quality == "INVALID" or trade_date in seen:
            continue
        seen[trade_date] = Candle(trade_date, c["open"], c["high"], c["low"], c["close"], quality)
    return [seen[d] for d in sorted(seen)]
