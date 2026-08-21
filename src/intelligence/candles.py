"""Platform Candle Builder — PRE-SP-C.14A

Deterministic candle aggregation from canonical price observations.
No interpolation. No forward-fill. Point-in-time safe.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple

from database.connection import get_session
from database.models import PriceObservation, PlatformCandle
from database.repository import get_price_observations_by_instrument
from sqlalchemy import func

DEFAULT_TIMEFRAME = "30m"
TIMEFRAME_MINUTES = {"5m": 5, "15m": 15, "30m": 30, "1h": 60, "4h": 240, "1d": 1440}


def _timeframe_delta(timeframe: str) -> timedelta:
    return timedelta(minutes=TIMEFRAME_MINUTES.get(timeframe, 30))


def _bucket_start(dt: datetime, timeframe: str) -> datetime:
    """Floor datetime to bucket boundary."""
    minutes = TIMEFRAME_MINUTES.get(timeframe, 30)
    total_minutes = (dt.hour * 60 + dt.minute)
    bucket_minutes = (total_minutes // minutes) * minutes
    return dt.replace(hour=bucket_minutes // 60, minute=bucket_minutes % 60, second=0, microsecond=0)


def build_candles_from_observations(
    platform: str,
    instrument: str,
    timeframe: str = DEFAULT_TIMEFRAME,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    quote_side: str = "SINGLE",
    min_observations: int = 1,
) -> List[Dict[str, Any]]:
    """Build deterministic candles from price observations.

    Args:
        platform: source platform name (matches price_observations.source)
        instrument: instrument code
        timeframe: candle timeframe
        start: optional start boundary
        end: optional end boundary
        quote_side: BUY, SELL, or SINGLE
        min_observations: minimum observations for a valid candle

    Returns:
        list of candle dicts
    """
    delta = _timeframe_delta(timeframe)

    # Fetch observations for this platform/instrument
    # Use a large limit to cover the range; filter by time locally
    obs = get_price_observations_by_instrument(instrument, limit=5000, hours=720)
    if not obs:
        return []

    # Filter to matching source and time range
    filtered = []
    for o in obs:
        if o.source != platform:
            continue
        if start and o.timestamp < start:
            continue
        if end and o.timestamp > end:
            continue
        filtered.append(o)

    if not filtered:
        return []

    # Sort by timestamp ascending
    filtered.sort(key=lambda x: x.timestamp)

    # Group into buckets
    buckets: Dict[datetime, List[PriceObservation]] = {}
    for o in filtered:
        bs = _bucket_start(o.timestamp, timeframe)
        buckets.setdefault(bs, []).append(o)

    candles = []
    for bs in sorted(b
