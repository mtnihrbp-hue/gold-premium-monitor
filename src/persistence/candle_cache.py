"""The daily candles, kept between runs (SP-D, SP_D_HANDOFF.md section 34).

Neon's free plan allows 5 GB of outbound transfer a month. Every scheduled run read tgju's daily
candles in full -- 18K up to three times, the dollar, world gold's 12,000 days -- about 26,000 rows a
run for history that only ever grows by one day. The candles are stored first-seen and never
revised (repository.save_daily_candles), so a copy kept between runs stays right: each read asks
only for the instrument's count and latest day, and fetches the days after the copy's when there
are new ones. A copy that disagrees in any other way is dropped and the instrument read in full.

On when CANDLE_CACHE_FILE names the file -- the workflow sets it and keeps the file in its cache
beside state.json. Unset (tests, local runs), every read goes to the database as before.
"""

import json
import os
from datetime import date

FIELDS = ("trade_date", "open", "high", "low", "close", "source_quality")


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
